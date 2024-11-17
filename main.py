import asyncio
from sys import stderr, platform

import aiofiles
from better_proxy.proxy import Proxy
from eth_account import Account
from eth_account.account import LocalAccount
from loguru import logger

from core import start_farm_account, parse_account_balance
from utils import loader

if platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

logger.remove()
logger.add(stderr, format='<white>{time:HH:mm:ss}</white>'
                          ' | <level>{level: <8}</level>'
                          ' | <cyan>{line}</cyan>'
                          ' - <white>{message}</white>')


async def main() -> any:
    tasks: list[asyncio.Task] = []

    match user_action:
        case 1:
            print()
            tasks: list[asyncio.Task] = [
                asyncio.create_task(coro=start_farm_account(account=current_account, proxy=current_proxy))
                for current_account, current_proxy in zip(accounts_list, proxy_list)
            ]

        case 2:
            generate_accounts_count: int = int(input('\nHow Many Accounts Do You Want To Generate: '))
            print()
            generated_accounts_list: list[str] = []

            for _ in range(generate_accounts_count):
                generated_accounts_list.append(Account.create().key.hex())

            async with aiofiles.open(
                    file='data/accounts.txt',
                    mode='a',
                    encoding='utf-8'
            ) as f:
                await f.write('\n'.join(generated_accounts_list) + '\n')

        case 3:
            threads: int = int(input('\nThreads: '))
            loader.semaphore = asyncio.Semaphore(value=threads)
            print()

            tasks: list[asyncio.Task] = [
                asyncio.create_task(coro=parse_account_balance(account=current_account, proxy=current_proxy))
                for current_account, current_proxy in zip(accounts_list, proxy_list)
            ]

        case _:
            print()
            pass

    return await asyncio.gather(*tasks)


if __name__ == '__main__':
    with open(file='data/accounts.txt',
              mode='r',
              encoding='utf-8') as file:
        accounts_list: list[LocalAccount] = [Account.from_key(private_key=row.strip()) for row in file]

    with open(file='data/proxies.txt',
              mode='r',
              encoding='utf-8') as file:
        proxy_list: list[str] = [Proxy.from_str(proxy=row.strip().replace('https://', 'http://') if
        '://' in row.strip() else f'http://{row.strip()}').as_url for row in file]

    logger.success(f'Successfully Loaded {len(accounts_list)} Accounts // {len(proxy_list)} Proxies')

    limit: int = min(len(accounts_list), len(proxy_list))
    accounts_list: list[LocalAccount] = accounts_list[:limit]
    proxy_list: list[str] = proxy_list[:limit]

    user_action: int = int(input('\n1. Start Farming'
                                 '\n2. Generate Accounts'
                                 '\n3. Parse Accounts Balance'
                                 '\nEnter Your Action: '))

    try:
        import uvloop

        tasks_result: tuple = uvloop.run(main())

    except ModuleNotFoundError:
        tasks_result: tuple = asyncio.run(main())

    if user_action == 3:
        mgf_balance = sum(x[0] for x in tasks_result)
        usdc_balance = sum(x[1] for x in tasks_result)

        logger.info(f'Total Balances | MGF: {mgf_balance} | USDC: {usdc_balance}')

    logger.success('The Work Has Been Successfully Finished')
    input('\nPress Enter to Exit..')
