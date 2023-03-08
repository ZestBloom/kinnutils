from algosdk.encoding import encode_address, decode_address
import multihash
from cid import CIDv0, CIDv1, make_cid


def address2cid(address):
    """
    Converts algorand address to ipfs cid for arc19 asset parsing.
    """
    dec_bytes = decode_address(address)
    return CIDv0(multihash.encode(dec_bytes, "sha2-256", length=32)).encode().decode()


def cid2address(hash):
    return encode_address(multihash.decode(make_cid(hash).multihash).digest)


def cid_from_asset(params):
    """
    Converts and parses algorand asset from indexer query (search_asset) to ipfs cid for arc19 asset parsing.
    """
    url = params["url"]
    if "template-ipfs" in url:
        # parsing arc19 data
        url_parsed = url.split(":")
        version = int(
            url_parsed[-4]
        )  # may not be necessary, both v=0 and v=1 correctly resolve at ipfs gateway
        codec = url_parsed[-3]
        field = url_parsed[-2]
        code = url_parsed[-1].split("}")[0]  # remove closing bracket
        dec_bytes = decode_address(params[field])
        if version == 0:
            return CIDv0(multihash.encode(dec_bytes, code, length=32)).encode().decode()
        else:
            # below works for codec=='raw', haven't tested other types
            return (
                CIDv1(codec, multihash.encode(dec_bytes, code, length=32))
                .encode("base32")
                .decode()
            )
    else:
        raise (
            TypeError(
                "Not an arc19 asset, or check that the url is structured: \
                        template-ipfs://{ipfscid:0:dag-pb:reserve:sha2-256}"
            )
        )
