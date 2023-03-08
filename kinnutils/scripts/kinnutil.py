import os
import sys
sys.path.insert(0, os.path.normpath(os.path.join(__file__, "../..")))

import click

from algorand import account_utils

def send_transaction(txn, dryrun=False):
    if dryrun:
        click.echo("Dry run. Not sending transaction.")
    else:
        algodcli = account_utils.get_algod()
        txid = algodcli.send_transaction(txn)
        click.echo(f"Transaction sent: {txid}")

def pause(cont=True):
    if cont:
        input("press enter to continue... (or ctrl-c to cancel)")

@click.group()
def cli():
    pass


@click.command()
def generate_wallet():
    """Generate a new wallet and print the mnemonic phrase."""
    address, mnmc = account_utils.generate_new_account()
    click.echo("Write down your new mnemonic phrase. You will need it to recover your wallet. Keep it safe!")
    click.echo("[" + click.style(address, fg="red") + "]")
    click.echo(click.style(mnmc, fg="red"))


@click.command()
@click.option("-c", "--create-new", is_flag=True, default=False, help="Create a new wallet and transfer used for transfer out")
@click.option("-r", "--receiver", default=None, help="The address of the wallet to receive the funds. You will be prompted for this wallet's mnemonic phrase.")
@click.option("-d", "--dryrun", is_flag=True, default=False, help="Perform a dry run of the transfer out.")
@click.option("-y", "--yes", is_flag=True, default=False, help="Skip confirmation prompts.")
def transfer_out(create_new, receiver, dryrun, yes):
    """Transfer all funds from the current wallet to a new wallet, performing opt in and close out of all assets."""
    if create_new:
        receiver, mnmc = account_utils.generate_new_account()
        receiver_account = account_utils.Account(pk=receiver, mnmc=mnmc)
        click.echo("Write down your new mnemonic phrase. You will need it to recover your wallet. Keep it safe!")
        click.echo("[" + click.style(receiver, fg="red") + "]")
        click.echo(click.style(mnmc, fg="red"))
        pause(cont=yes)
    else:
        if receiver:
            click.echo("You will be prompted for the mnemonic phrase of an authorized signer for the recipient wallet {reciever}")
            pause(cont=yes)
            receiver_account = account_utils.Account(pk=receiver, interactive=True)
        else:
            click.echo("You will be prompted for the mnemonic phrase and public address of the recipient wallet")
            pause(cont=yes)
            receiver_account = account_utils.Account(interactive=True)
            
    
    click.echo("You will now be prompted for public key, and the mnemonic phrase of an authorized signer for the wallet you wish to transfer out.")
    pause(cont=yes)
    close_out_account = account_utils.Account(interactive=True)
    close_out_assets_list = [item for item in close_out_account.assets.keys()]
    current_reciever_assets = [item for item in receiver_account.assets.keys()]
    
    # Check for Algos
    total_unique_assets = len(set(close_out_assets_list + current_reciever_assets))
    min_balance = .1 * 10**6 * total_unique_assets
    expected_num_txns = total_unique_assets - len(current_reciever_assets)

    initial_transfer_amount = min_balance - receiver_account.balance + 1000 * expected_num_txns
    if initial_transfer_amount > 0:
        # perform initial transfer
        click.echo(f"Seeding {reciever_account.pk} with {initial_transfer_amount} Algos")
        pause(cont=yes)
        stxn = close_out_account.gen_send_txn(receiver_account.address, initial_transfer_amount, sign=True)
        send_transaction(stxn, dryrun=dryrun)
     
    click.echo(f"Beginning Asset Transfer Out")
    click.echo("Assets to be transferred: {close_out_assets}")
    pause(cont=yes)
    close_account_assets = close_out_account.assets
    for asset in close_out_assets_list:
        amount = close_account_assets[asset]["amount"]
        
        if not receiver_account.has_asset(asset):
            # Opt in to asset
            click.echo(f"Opting in {receiver_account.pk} to asset {asset}")
            stxn = receiver_account.gen_asset_optin_txn(asset, sign=True)
            send_transaction(stxn, dryrun=dryrun)
        
        # Send and Close Out Asset
        click.echo(f"Sending {amount} of asset {asset} from {close_out_account.pk} to {receiver_account.pk}")
        stxn = close_out_account.gen_send_asset_txn(receiver_account.pk, amount, asset_id=asset, close_to=receiver_account.pk, sign=True)
        send_transaction(stxn, dryrun=dryrun)
    
    # send remaining algos
    remaining_balance = close_out_account.balance
    click.echo(f"Sending remaining {remaining_balance} Algos")
    pause(cont=yes)
    stxn =close_out_account.gen_send_txn(receiver_account.pk, remaining_balance, sign=True)
    send_transaction(stxn, dryrun=dryrun)
    click.echo("Transfer Out Complete")


cli.add_command(generate_wallet)
cli.add_command(transfer_out)


if __name__ == "__main__":
    cli()
