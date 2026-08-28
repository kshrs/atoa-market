"""
ATOA Agent Wallets & Reputation Router.
Provides wallet inspection and devnet faucet funding.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.models import WalletState, EventType
from backend.app.state import state_store
from backend.app.routers.events import ws_manager

router = APIRouter(prefix="/v1/wallets", tags=["wallets"])


class FaucetRequest(BaseModel):
    address: str = Field(..., example="0xWorker_Optimizer_B2")
    amount_usdc: float = Field(default=100.0, gt=0.0, le=10000.0)


@router.get("", response_model=List[WalletState])
async def list_wallets():
    """Retrieve all agent wallets, balances, locked stakes, and reputation metrics."""
    return await state_store.get_all_wallets()


@router.get("/{address}", response_model=WalletState)
async def get_wallet(address: str):
    """Retrieve specific agent wallet state and reputation."""
    wallet = await state_store.get_wallet(address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet for address '{address}' not found."
        )
    return wallet


@router.post("/faucet", response_model=WalletState)
async def fund_wallet_faucet(faucet_in: FaucetRequest):
    """Devnet faucet to fund an agent wallet for live demo testing."""
    wallet = await state_store.get_or_create_wallet(faucet_in.address)
    wallet.balance_usdc += faucet_in.amount_usdc
    
    await ws_manager.broadcast_event(
        event_type=EventType.WALLET_UPDATED,
        data={
            "address": wallet.address,
            "balance_usdc": wallet.balance_usdc,
            "locked_collateral_usdc": wallet.locked_collateral_usdc,
            "reputation_score": wallet.reputation_score,
        }
    )
    
    return wallet
