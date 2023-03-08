from abc import ABC, abstractmethod
from typing import Union, List


class AccountBase(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def _generate_account(self):
        pass

    @property
    @abstractmethod
    def pk(self):
        pass

    @property
    @abstractmethod
    def sk(self):
        pass

    @abstractmethod
    def info(self):
        pass

    @property
    @abstractmethod
    def assets(self):
        pass

    @property
    @abstractmethod
    def created_assets(self):
        pass

    @property
    @abstractmethod
    def created_nfts(self):
        pass

    @property
    @abstractmethod
    def created_fts(self):
        pass

    @property
    @abstractmethod
    def balance(self):
        pass

    @abstractmethod
    def filter_assets(self, _func):
        pass

    @abstractmethod
    def get_asset_bal(self, asset_id):
        pass

    # ************ NEED TO CHECK ALL METHODS BELOW FOR OTHER NETWORKS ************
    @abstractmethod
    def gen_asset_optin_txn(self, asset_id, sign=False):
        pass

    @abstractmethod
    def gen_destroy_asset_txn(self, asset_id, sign=False):
        pass

    @abstractmethod
    def gen_send_txn(self, recipient, amount):
        pass

    @abstractmethod
    def gen_send_asset_txn(self, asset_id, receiver, qty):
        pass

    @abstractmethod
    def gen_revoke_asset_txn(self, asset_id, receiver, revoke_from, qty, sign=False):
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def gen_freeze_txn(self, asset_id, target_acct, target_state=True, sign=False):
        # create the asset freeze transaction
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def gen_asset_close_out_txn(self, asset_id, close_to=None, sign=False):
        pass
