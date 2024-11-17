import asyncio

from curl_cffi.requests import AsyncSession, Response
from eth_account.account import LocalAccount
from eth_account.messages import encode_defunct
from loguru import logger
from pyuseragents import random as random_useragent
from tenacity import retry

from utils import loader


def log_retry_error(retry_state):
    logger.error(retry_state.outcome.exception())


class Farmer:
    def __init__(self,
                 account: LocalAccount,
                 proxy: str) -> None:
        self.account: LocalAccount = account
        self.proxy: str = proxy

    async def _get_client(self) -> AsyncSession:
        client: AsyncSession = AsyncSession(
            impersonate='chrome110',
            proxies={
                'http': self.proxy,
                'https': self.proxy
            },
            headers={
                'user-agent': random_useragent(),
                'accept': '*/*',
                'accept-language': 'ru,en;q=0.9,vi;q=0.8,es;q=0.7,cy;q=0.6',
                'origin': 'https://app.megafin.xyz',
                'referer': 'https://app.megafin.xyz/'
            }
        )

        return client

    @retry(after=log_retry_error)
    async def _profile_request(self,
                               client: AsyncSession) -> None:
        r: Response = await client.get(url='https://api.megafin.xyz/users/profile')

        if 'title>Access denied | api.megafin.xyz used Cloudflare to restrict access</title>' in r.text:
            raise ValueError(f'{self.account.address} | CloudFlare')

        if not r.ok or not r.json().get('result', ''):
            raise ValueError(f'{self.account.address} | Wrong Response When Profile: {r.text}')


    @retry(after=log_retry_error)
    async def _login_account(self,
                             client: AsyncSession) -> str:
        sign_text: str = f'megafin.xyz requests you to sign in with your wallet address: {self.account.address}'
        sign_hash: str = self.account.sign_message(signable_message=encode_defunct(text=sign_text)).signature.hex()

        r: Response = await client.post(url='https://api.megafin.xyz/auth',
                                        json={
                                            'invite_code': '133d76e4',
                                            'key': sign_text,
                                            'wallet_hash': sign_hash
                                        })

        if 'title>Access denied | api.megafin.xyz used Cloudflare to restrict access</title>' in r.text:
            raise ValueError(f'{self.account.address} | CloudFlare')

        if not r.ok or not r.json().get('result', {}).get('token', ''):
            raise ValueError(f'{self.account.address} | Wrong Response When Auth: {r.text}')

        return r.json().get('result', {}).get('token', '')

    @retry(after=log_retry_error)
    async def _send_connect_request(self,
                                    client: AsyncSession) -> tuple[float, float]:
        r: Response = await client.get(url='https://api.megafin.xyz/users/connect')

        if 'title>Access denied | api.megafin.xyz used Cloudflare to restrict access</title>' in r.text:
            raise ValueError(f'{self.account.address} | CloudFlare')

        if not r.ok or not r.json().get('result', {}).get('balance', ''):
            raise ValueError(f'{self.account.address} | Wrong Response When Pinging: {r.text}')

        return r.json()['result']['balance']['MGF'], r.json()['result']['balance']['USDC']

    async def farm_account(self) -> None:
        client: AsyncSession = await self._get_client()
        auth_token: str = await self._login_account(client=client)
        client.headers.update({
            'authorization': f'Bearer {auth_token}'
        })
        await self._profile_request(client=client)

        while True:
            mgf_balance, usdc_balance = await self._send_connect_request(client=client)
            logger.info(f'{self.account.address} | MGF: {mgf_balance} | USDC: {usdc_balance}, sleeping 90 secs.')
            await asyncio.sleep(delay=90)

    async def parse_account_balance(self) -> tuple[float, float]:
        client: AsyncSession = await self._get_client()
        auth_token: str = await self._login_account(client=client)
        client.headers.update({
            'authorization': f'Bearer {auth_token}'
        })
        await self._profile_request(client=client)

        mgf_balance, usdc_balance = await self._send_connect_request(client=client)
        logger.success(f'{self.account.address} | MGF: {mgf_balance} | USDC: {usdc_balance}')

        return mgf_balance, usdc_balance


async def start_farm_account(account: LocalAccount,
                             proxy: str) -> None:
    farmer: Farmer = Farmer(account=account,
                            proxy=proxy)
    return await farmer.farm_account()


async def parse_account_balance(account: LocalAccount,
                                proxy: str) -> tuple[float, float]:
    async with loader.semaphore:
        farmer: Farmer = Farmer(account=account,
                                proxy=proxy)
        return await farmer.parse_account_balance()
