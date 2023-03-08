import os
import re
import time
import magic
import structlog
import requests
from io import BytesIO

from requests.exceptions import ConnectionError
from decorators import retry
from core.settings import settings


IPFS_GATEWAY = settings.IPFS_GATEWAY
EXTRA_IPFS_GATEWAYS = [IPFS_GATEWAY]
LOGGER = structlog.get_logger()


def contains_cid(path):
    p = r"Qm[1-9A-HJ-NP-Za-km-z]{44,}|b[A-Za-z2-7]{58,}|B[A-Z2-7]{58,}|z[1-9A-HJ-NP-Za-km-z]{48,}|F[0-9A-F]{50,}"
    return re.search(p, path) is not None


class IPFSGatewayError(Exception):
    pass


class PinataPinningError(Exception):
    pass


class PinataUnpinningError(Exception):
    pass


class PinataHashMetadataError(Exception):
    pass


class InvalidCIDError(Exception):
    pass


class NonMediaHTTPLink(Exception):
    pass


def get_mime(raw):
    """Helper function to quickly get the image MIME type"""
    mime = magic.from_buffer(raw)
    fts = {
        "JPEG": "jpg",
        "GIF": "gif",
        "PNG": "png",
        "Web/P": "webp",
        "TIFF": "tif",
        "MP4": "mp4",
        ".MOV": "mov",
    }  # supported filetypes

    for ft, ext in fts.items():
        if ft in mime:
            return "." + ext

    return False  # if file type unrecognized, returns false


class IPFSCacher():
    gateways = EXTRA_IPFS_GATEWAYS
    _cid = None
    _lockfile = "/tmp/ipfs_gateway"
    _gindex = 0

    def __init__(self, cid_url):  # noqa
        self._cid_path = cid_url
        if not self.cid:
            raise InvalidCIDError(f"{cid_url} does not contain a CID")

        if not os.path.exists(self._lockfile):
            self._update_lockfile()
        else:
            self._read_lockfile()

    @property
    def cid(self):
        if self._cid is None:
            p = r"Qm[1-9A-HJ-NP-Za-km-z]{44,}(\/[a-zA-Z0-9._\-+%\ ]*)*(\.)?([a-zA-Z0-9]){0,4}|b[A-Za-z2-7]{58,}(\/[a-zA-Z0-9._\-+%\ ]*)*(\.)?([a-zA-Z0-9]){0,4}|B[A-Z2-7]{58,}(\/[a-zA-Z0-9._\-+%\ ]*)*(\.)?([a-zA-Z0-9]){0,4}|z[1-9A-HJ-NP-Za-km-z]{48,}(\/[a-zA-Z0-9._\-+%\ ]*)*(\.)?([a-zA-Z0-9]){0,4}|F[0-9A-F]{50,}(\/[a-zA-Z0-9._\-+%\ ]*)*(\.)?([a-zA-Z0-9]){0,4}"
            match = re.search(p, self._cid_path)
            if match:
                self._cid = match.group()
            else:
                self._cid = ""
        return self._cid

    @property
    def url(self):
        return f"{self.gateways[self._gindex]}/{self.cid}"

    def _swap_gw(self):
        """
        Helper methods that increments the IPFS Gateway index to use for the
        next asset download attempt.
        """
        self._gindex += 1
        self._gindex = self._gindex % len(self.gateways)
        self._update_lockfile()

    def _update_lockfile(self):
        """
        Helper method to write IPFS Gateway Index to lockfile for next use.
        """
        with open(self._lockfile, "w") as f:
            f.write(f"{self._gindex}")

    def _read_lockfile(self):
        """
        Helper method to read last used IPFS Gateway Index from lockfile

        :return: int
        """
        try:
            with open(self._lockfile, "r") as f:
                self._gindex = int(f.read().strip())
        except ValueError as e:
            self._update_lockfile()

    @retry(
        IPFSGatewayError, tries=len(EXTRA_IPFS_GATEWAYS), delay=3, backoff=1, logger=LOGGER
    )
    def fetch_content(self):
        """
        Method which performs https download of content from IPFS.

        This method attempts to detect various errors with fetching IPFS content
        and is decorated with retry to cycle through different gateway
        providers.

        :return: bytes
        """
        log_info = {"gateway": self.gateways[self._gindex], "cid": self.cid}

        try:
            self._swap_gw()
            req = requests.get(self.url, timeout=10)
            assert req.ok
        except ConnectionError as e:
            # let the retry handle this
            LOGGER.error("IPFS Fetch Error", exception=type(e).__name__, **log_info)
            raise IPFSGatewayError("Connection Error Occurred")
        except AssertionError as e:
            LOGGER.error("IPFS Fetch Error", exception=type(e).__name__, **log_info)
            raise IPFSGatewayError("Content Request Failed")
        except requests.exceptions.ReadTimeout as e:
            LOGGER.error("IPFS Fetch Error", exception=type(e).__name__, **log_info)
            raise IPFSGatewayError("Read Timeout Occurred")
        except requests.exceptions.ChunkedEncodingError as e:
            LOGGER.error("IPFS Fetch Error", exception=type(e).__name__, **log_info)
            raise IPFSGatewayError("Chunked Encoding Error Occurred")
        except Exception as e:
            LOGGER.error("IPFS Fetch Error", exception=type(e).__name__, **log_info)
            raise e

        content = req.content
        content_type = req.headers.get("Content-Type", "")
        if "text" in content_type or "html" in content_type:
            contentstr = req.text
            if (
                "Gateway Time-out" in contentstr
                or "Cloudflare" in contentstr
                or "too many requests" in contentstr
            ):
                LOGGER.error("Blocked by CloudFlare", reason=contentstr, **log_info)
                raise IPFSGatewayError("Failed to Request Content")

        log_info["mime"] = content_type
        log_info["status_code"] = req.status_code
        LOGGER.info("IPFS Fetched Asset", **log_info)

        return content

    def get_mime(self, content):
        return get_mime(content)


class DownloadedAsset:
    file: BytesIO = None
    _content = None
    _content_mime = None
    _cid = None

    def __init__(self, url, force=False):
        """
        Init method for Download Asset class. The asset is immediately
        downloaded and important asset contexts are saved to the instance
        properties for later use.
        """
        # handle URL Shorteners and Arweave
        if "bit.ly" in url or "tinyurl" in url or "arweave.net" in url:
            # fetch head and final link
            req = requests.head(url)
            self.url = req.headers["Location"]
        else:
            self.url = url

        self.fetch_content(force)

        if self.mime == "text/html":
            content = str(self.raw_content)
            if (
                "Gateway Time-out" in content
                or "Cloudflare" in content
                or "too many requests" in content
            ):
                raise IPFSGatewayError("Failed to Request Content")
        try:
            self.file = BytesIO(self.raw_content)
        except TypeError as e:
            LOGGER.error(
                "BytesIO Failure", mime=self.mime, url=url, exception="TypeError"
            )
            raise e
        except Exception as e:
            LOGGER.error("BytesIO Failure", mime=self.mime, url=url)
            raise e

    @property
    def cid(self):
        return self._cid

    @property
    def mime(self):
        if self._content_mime is None:
            if self._content is None:
                req = requests.head(self.url)
                self._content_mime = req.headers["Content-Type"]
            else:
                mime = magic.Magic(mime=True)
                self._content_mime = str(mime.from_buffer(self._content))

        return self._content_mime

    def fetch_content(self):
        """
        Helper method to perform HTTP Download of the specified asset url.

        Depending on whether an IPFS CID is detected, this may use a standard
        HTTP get request, or the IPFSCacher class.

        :return: None
        """
        log_info = {"url": self.url}
        starttime = time.time()
        if contains_cid(self.url):
            ipfc = IPFSCacher(self.url)
            self._content = ipfc.fetch_content()
            self._cid = ipfc.cid
        else:
            log_info["mime"] = self.mime
            if "image" in self.mime or "animation" in self.mime:
                rq = requests.get(self.url, allow_redirects=True)
                self._content = rq.content
            else:
                LOGGER.warning("Unknown Http Link", **log_info)
                raise NonMediaHTTPLink("Unknown Http Link")

        endtime = time.time()
        LOGGER.debug("Fetched Asset", elapsed=(endtime - starttime), **log_info)

    def to_file(self, fpath):
        """Helper method to write the instance's downloaded bytes to file"""
        if self.file is not None:
            with open(fpath, "wb") as f:
                f.write(self.file.getbuffer())

    @property
    def raw_content(self):
        if self._content is None:
            self.fetch_content()
        return self._content

    @property
    def can_process(self):
        fts = [
            "image/png",
            "image/jpeg",
            "image/tif",
            "image/webp",
            "image/gif",
            "video/3gpp",
            "video/mp4",
            "video/mov",
            "video/quicktime",
        ]  # supported mime types

        return self.mime in fts

    @property
    def is_audio(self):
        return "audio/" in self.mime

    @property
    def is_video(self):
        return "video/" in self.mime

    @property
    def is_animation(self):
        return self.is_video and self.is_audio

    @property
    def is_image(self):
        return "image/" in self.mime


def download_asset(media_url: str, force=False) -> DownloadedAsset:
    """
    Uses the Asset Media URL to create a Downloaded Asset class instance,
    which provides some extra context about the downloaded media.

    ::param media_url::
    ::return:: DownloadedAsset
    """
    return DownloadedAsset(url=media_url, force=force)


