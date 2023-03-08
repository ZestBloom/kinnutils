from getpass import getpass
from typing import Union, List
import structlog

from algosdk import account, mnemonic

from algosdk.transaction import (
    AssetTransferTxn,
    AssetFreezeTxn,
    PaymentTxn,
    AssetConfigTxn,
    ApplicationCreateTxn,
    ApplicationDeleteTxn,
    AssetCloseOutTxn,
    SignedTransaction,
)
from algosdk.error import IndexerHTTPError

from core.factory import AccountFactory
from core.accounts_base import AccountBase

from algorand.algoconn import IndexerBase, get_algod
from decorators import retry

logger = structlog.get_logger()


@AccountFactory.register("algo")
class Account(AccountBase, IndexerBase):
    _pk = None
    _sk = None

    def __init__(self, mnmc=None, algocli=None, pk=None, testnet=False, interactive=False):
        IndexerBase.__init__(self, testnet=testnet)
        if algocli is None:
            self.algodcli = get_algod(testnet=testnet)
        else:
            self.algodcli = algocli

        if interactive and mnmc is None:
            mnmc = mnemonic.to_private_key(getpass("Enter authorized signer mnemonic: ").replace(",", ""))
        
        if mnmc and self._sk is None:
            self._sk = mnemonic.to_private_key(mnmc)
        
        if pk is not None:
            self._pk = pk
        elif interactive and pk is None:
            suggested_pk = account.address_from_private_key(self._sk)
            input_pk = input(f"Enter account public key ({pk}): ")
            if input_pk:
                self._pk = input_pk
            else:
                self._pk = suggested_pk
        elif pk is None and self._sk:
            self._pk = account.address_from_private_key(self._sk)
            

    def _generate_account(self):
        self._sk, self._pk = account.generate_account()

    @property
    def pk(self):
        return self._pk

    @property
    def sk(self):
        return self._sk

    def _get_mnemonic(self):
        return mnemonic.from_private_key(self.sk)

    @retry(IndexerHTTPError, tries=2, delay=1, backoff=1, logger=logger)
    def info(self):
        try:
            info = self.indexer.account_info(self.pk, exclude="all")
            self.use_fallback = False
        except IndexerHTTPError as e:
            if "no accounts found for address" in str(e):
                return {}
            else:
                self.use_fallback = True
                raise e

        return info

    @retry(IndexerHTTPError, tries=4, delay=1, backoff=1, logger=logger)
    def _get_account_assets_page(self, next_token=None):
        try:
            return self.indexer.lookup_account_assets(self.pk, next_page=next_token)
        except IndexerHTTPError as e:
            self.use_fallback = True
            raise e

    @retry(IndexerHTTPError, tries=4, delay=1, backoff=1, logger=logger)
    def _get_created_assets_page(self, next_token=None):
        try:
            return self.indexer.lookup_account_asset_by_creator(
                self.pk, next_page=next_token
            )
        except IndexerHTTPError as e:
            self.use_fallback = True
            raise e

    def params(self):
        params = self.algodcli.suggested_params()
        params.fee = 1000
        params.flat_fee = True

        return params

    @property
    def assets(self):
        res = self._get_account_assets_page()
        assets = {asset.pop("asset-id"): asset for asset in res["assets"]}

        while "next-token" in res:
            res = self._get_account_assets_page(next_token=res["next-token"])
            assets.update({asset.pop("asset-id"): asset for asset in res["assets"]})

        return assets

    @property
    def created_assets(self):
        res = self._get_created_assets_page()
        assets = {asset.pop("index"): asset for asset in res["assets"]}

        while "next-token" in res:
            res = self._get_created_assets_page(next_token=res["next-token"])
            assets.update({asset.pop("index"): asset for asset in res["assets"]})

        # for asst in assets.values():
        #    asst["managerkey"] = asst.get("manager", None)
        #    asst["freezeaddr"] = asst.get("freeze", None)
        return assets

    def get_available_assets(self, req_qty):
        return [
            asset for asset, info in self.assets.items() if info["amount"] >= req_qty
        ]

    @property
    def created_applications(self):
        return [app["id"] for app in self.info()["created-apps"]]

    @property
    def created_nfts(self):
        return [
            key for key, value in self.created_assets.items() if value["total"] == 1
        ]

    @property
    def created_fts(self):
        return [key for key, value in self.created_assets.items() if value["total"] > 1]

    @property
    def algos(self):
        return self.info().get("amount")

    @property
    def balance(self):
        return self.info().get("amount") or self.info().get("account", {}).get("amount")

    def has_asset(self, asset_id):
        return (asset_id in self.assets)

    def filter_assets(self, _func):
        return {
            key: value for key, value in self.created_assets.items() if _func(value)
        }

    def get_asset_bal(self, asset_id):
        return self.assets.get(asset_id, {}).get("amount", None)

    def gen_asset_optin_txn(self, asset_id, sign=False):

        txn = AssetTransferTxn(self.pk, self.params(), self.pk, 0, asset_id)

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_destroy_asset_txn(self, asset_id, sign=False):

        txn = AssetConfigTxn(
            sender=self.pk,
            sp=self.params(),
            index=asset_id,
            strict_empty_address_check=False,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_send_txn(
        self, recipient, amount, close_remainder_to=None, rekey_to=None, sign=False
    ):

        txn = PaymentTxn(
            self.pk,
            self.params(),
            recipient,
            amount,
            close_remainder_to=close_remainder_to,
            rekey_to=rekey_to,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_send_asset_txn(self, asset_id, receiver, qty, close_to=None, sign=False):

        txn = AssetTransferTxn(
            self.pk, self.params(), receiver, qty, asset_id, close_assets_to=close_to
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_revoke_asset_txn(self, asset_id, receiver, revoke_from, qty, sign=False):

        # Fixme - Do we really want close assets to?
        txn = AssetTransferTxn(
            self.pk,
            self.params(),
            receiver,
            qty,
            asset_id,
            revocation_target=revoke_from,
            close_assets_to=receiver,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_asset_update_txn(
        self,
        asset_id,
        mgr_address,
        rsv_address,
        freeze_address,
        claw_address,
        sign=False,
    ):
        """Assemble an asset update transaction.

        Note: this account must be the manager of the target asset.
        :return:
        """

        txn = AssetConfigTxn(
            self.pk,
            self.params(),
            manager=mgr_address,
            reserve=rsv_address,
            freeze=freeze_address,
            clawback=claw_address,
            index=asset_id,
            strict_empty_address_check=False,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_freeze_txn(self, asset_id, target_acct, target_state=True, sign=False):
        # create the asset freeze transaction

        txn = AssetFreezeTxn(
            self.pk,
            self.params(),
            index=asset_id,
            target=target_acct,
            new_freeze_state=target_state,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_create_asset_txn(
        self,
        asset_name,
        unit_name,
        total,
        url=None,
        default_frozen=False,
        metadata_hash=None,
        manager=None,
        reserve=None,
        freeze=None,
        clawback=None,
        decimals=0,
        note=None,
        sign=False,
    ):

        txn = AssetConfigTxn(
            sender=self.pk,
            sp=self.params(),
            total=total,
            default_frozen=default_frozen,
            unit_name=unit_name,
            asset_name=asset_name,
            url=url,
            metadata_hash=metadata_hash,
            manager=manager,
            reserve=reserve,
            freeze=freeze,
            clawback=clawback,
            decimals=decimals,
            note=note,
            strict_empty_address_check=False,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_create_app_txn(
        self,
        on_complete,
        approval_program,
        clear_program,
        global_schema,
        local_schema,
        app_args=None,
        sign=False,
    ):
        # create unsigned transaction
        txn = ApplicationCreateTxn(
            self.pk,
            sp=self.params(),
            on_complete=on_complete,
            approval_program=approval_program,
            clear_program=clear_program,
            global_schema=global_schema,
            local_schema=local_schema,
            app_args=app_args,
        )
        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_delete_app_txn(
        self,
        app_id: int = None,
        app_args: List[bytes] = None,
        foreign_accounts: List[str] = None,
        foreign_apps: List[int] = None,
        foreign_assets: List[int] = None,
        note: str = None,
        lease: bytes = None,
        rekey_to: str = None,
        sign: bool = True,
    ) -> Union[ApplicationCreateTxn, SignedTransaction]:
        # create unsigned delete app txn
        """Generate a Delete Application Call given some known context from
        this Account Instance.

        :param app_id: the application to update
        :param app_args: any additional arguments to the application
        :param foreign_accounts: any additional accounts to supply to the application
        :param foreign_apps: any other apps used by the application, identified by app index
        :param foreign_assets: list of assets involved in call
        :param note: transaction note field
        :param lease: transaction lease field
        :param rekey_to: rekey-to field, see Transaction
        :param sign:
        """
        txn = ApplicationDeleteTxn(
            sender=self.pk,
            sp=self.params(),
            index=app_id,
            app_args=app_args,
            accounts=foreign_accounts,
            foreign_apps=foreign_apps,
            foreign_assets=foreign_assets,
            note=note,
            lease=lease,
            rekey_to=rekey_to,
        )

        if sign:
            return txn.sign(self.sk)
        else:
            return txn

    def gen_asset_close_out_txn(self, asset_id, close_to=None, sign=False):
        if close_to is None:
            close_to = self.pk

        txn = AssetCloseOutTxn(self.pk, self.params(), close_to, asset_id)
        if sign:
            return txn.sign(self.sk)
        else:
            return txn


def generate_new_account():
    sk, pk = account.generate_account()
    mnmc = mnemonic.from_private_key(sk)
    return pk, mnmc
