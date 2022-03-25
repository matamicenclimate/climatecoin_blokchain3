# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *

from pyteal_utils import aoptin, axfer, ensure_opted_in

TEAL_VERSION = 6

return_prefix = Bytes("base16", "0x151f7c75")  # Literally hash('return')[:4]

# Global Vars
NFT_MINTER_ADDRESS=Bytes('nft_minter_address')
ORACLE_ADDRESS=Bytes('oracle_address')
CLIMATECOIN_ASA_ID=Bytes('climatecoin_asa_id')

swap_nft_to_fungible_selector = MethodSignature(
    "swap_nft_to_fungible(asset,uint64)uint64"
)
@Subroutine(TealType.uint64)
def swap_nft_to_fungible():
    transfer_txn = Gtxn[0]
    oracle_txn = Gtxn[1]

    valid_swap = Seq([
        Assert(Global.group_size() == Int(3)),
        #  this application serves as the escrow for the fee
        Assert(transfer_txn.type_enum() == TxnType.AssetTransfer),
        Assert(transfer_txn.xfer_asset() == Btoi(Txn.application_args[1])),
        # Assert(payment_txn.type_enum() == TxnType.Payment),
        # Assert(payment_txn.amount() == App.globalGet(GLOBAL_SERVICE_FEE)),
    ])

    nft_value = oracle_txn.application_args[1]
    return Seq(
        valid_swap,
        ensure_opted_in(Txn.application_args[1]),
        axfer(Txn.sender(), App.globalGet(CLIMATECOIN_ASA_ID), nft_value),
        Int(1)
    )

mint_climatecoin_selector = MethodSignature(
    "mint_climatecoin()uint64"
)
@Subroutine(TealType.uint64)
def mint_climatecoin():
    mint_welformed = Txn.application_args.length() == Int(4)
    return Seq(
        InnerTxnBuilder.Begin(),    
        # This method accepts a dictionary of TxnField to value so all fields may be set 
        InnerTxnBuilder.SetFields({ 
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_name: Bytes("Climatecoin"),
            TxnField.config_asset_unit_name: Bytes("CC"),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_total: Int(150_000_000),
            TxnField.config_asset_decimals: Int(0),
            TxnField.fee: Int(0),
        }),
        # Submit the transaction we just built
        InnerTxnBuilder.Submit(),   
        App.globalPut(CLIMATECOIN_ASA_ID, InnerTxn.created_asset_id()),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        Int(1)
    )

set_minter_address_selector = MethodSignature(
    "set_minter_address(address)address"
)
@Subroutine(TealType.uint64)
def set_minter_address():
    return Seq(
        App.globalPut(NFT_MINTER_ADDRESS, Txn.application_args[1]),
        Log(Concat(return_prefix, Txn.application_args[1])),
        Int(1)
    )

set_swap_price_selector = MethodSignature(
    "set_swap_price(uint64)uint64"
)
@Subroutine(TealType.uint64)
def set_swap_price():
    is_request_from_oracle = Txn.sender() == App.globalGet(ORACLE_ADDRESS),
    return Seq(
        Log(Concat(return_prefix, Txn.application_args[1])),
        Int(1)
    )

set_oracle_address_selector = MethodSignature(
    "set_oracle_address(address)address"
)
@Subroutine(TealType.uint64)
def set_oracle_address():
    return Seq(
        App.globalPut(ORACLE_ADDRESS, Txn.application_args[1]),
        Log(Concat(return_prefix, Txn.application_args[1])),
        Int(1)
    )

def contract():
    def initialize_vault():
        return Seq(
            # App.globalPut(NFT_MINTER_ADDRESS, Itob(Int(0))),
            App.globalPut(CLIMATECOIN_ASA_ID, Int(0)),            
            Int(1)
        )

    from_creator = Txn.sender() == Global.creator_address()

    handle_noop = Cond(
        [And(Txn.application_args[0] == mint_climatecoin_selector, from_creator), mint_climatecoin()],
        [And(Txn.application_args[0] == set_minter_address_selector, from_creator), set_minter_address()],
        [And(Txn.application_args[0] == set_oracle_address_selector, from_creator), set_oracle_address()],
        [Txn.application_args[0] == swap_nft_to_fungible_selector, swap_nft_to_fungible()],
        [Txn.application_args[0] == set_swap_price_selector, set_swap_price()],
    )

    program = Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), Return(initialize_vault())],
        #  allow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Reject()],
        [Txn.on_completion() == OnComplete.CloseOut, Reject()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, Return(handle_noop)]
    )

    return compileTeal(program, Mode.Application, version=TEAL_VERSION)

def contract_clear():
    return compileTeal(Approve(), Mode.Application, version=TEAL_VERSION)

if __name__ == '__main__':
    filename = 'climatecoin_vault.teal'
    with open(filename, 'w') as f:
        compiled = contract()
        f.write(compiled)
        print(f'compiled {filename}')

    filename = 'climatecoin_vault_clear.teal'
    with open(filename, 'w') as f:
        compiled = contract_clear()
        f.write(compiled)
        print(f'compiled {filename}')