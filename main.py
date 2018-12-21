import argparse
import asyncio
import os
import time
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial
from itertools import chain
from multiprocessing import cpu_count
from typing import Callable
from typing import List

import aiofiles
import uvloop
from aiohttp import ClientError
from aiohttp import ClientSession
from bs4 import BeautifulSoup

from config import logger
from config import settings

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
parser = argparse.ArgumentParser(
    prog='John Kenn gallery downloader',
    usage='See README.md',
    description='Simple script which download all images from John Kenn blog',
)
parser.add_argument('--path', help='path to saving images', default=os.path.dirname(__file__))
parser.add_argument('--dir-name', help='name of directory for images', default='media')
args = parser.parse_args()

MEDIA_DIR_NAME = args.dir_name
PWD = args.path
MEDIA_PATH = os.path.join(PWD, MEDIA_DIR_NAME)


def check_dir() -> None:
    if not os.path.exists(MEDIA_PATH):
        os.mkdir(MEDIA_PATH)


async def fetch_all_pages_url(session: ClientSession,
                              run_in_executor: Callable) -> List[str]:
    logger.info('--- Fetching all urls... ---')
    async with session.get(settings.BASE_URL) as response:
        if response.status != 200:
            raise ClientError('Status code non equal 200')
        response_text = await response.text()
        soup = await run_in_executor(BeautifulSoup, response_text, 'lxml')
        tag = await run_in_executor(
            soup.find,
            settings.ARCHIVE_LIST_TAG,
            {'class': settings.ARCHIVE_LIST_SELECTOR}
        )
        result = [url.attrs.get('href') for url
                  in await run_in_executor(tag.findAll, 'a')]

        logger.info(f'--- Found {len(result)} url(s) ---')
        return result


async def fetch_images_urls(semaphore: asyncio.Semaphore,
                            session: ClientSession, url: str,
                            run_in_executor: Callable) -> List[str] or None:
    async with semaphore:
        logger.info(f'--- Fetching images urls from {url} ---')
        async with session.get(url) as response:
            if response.status != 200:
                return
            response_text = await response.text()
            soup = await run_in_executor(BeautifulSoup, response_text, 'lxml')
            result = [img.attrs.get('src').replace('s320', 's1600') for img
                      in await run_in_executor(soup.findAll, 'img')
                      if 'jpg' in img.attrs.get('src')]

            logger.info(f'--- Found {len(result)} url(s) ---')
            return result


async def download_image(semaphore: asyncio.Semaphore,
                         session: ClientSession,
                         url: str, *_) -> None:
    async with semaphore:
        async with session.get(url) as response:
            logger.info(f'--- Downloading image from {url} ---')
            if response.status != 200:
                return
            file = await response.read()
            logger.info(f'--- Downloading from {url} is complete ---')
            filename = url.split('/')[-1]
    await save_image(file, filename)


async def save_image(data: bytes, filename: str) -> None:
    async with aiofiles.open(os.path.join(MEDIA_PATH, filename), 'wb') as out:
        logger.info(f'--- Saving image {filename} ---')
        await out.write(data)
        await out.flush()
        logger.info(f'--- Saving image {filename} is completed ---')


async def run_tasks(urls: List[str], session: ClientSession,
                    semaphore: asyncio.Semaphore, func: Callable,
                    run_in_executor: Callable = None) -> List[str] or None:
    logger.info(f'--- Creating tasks for func {func.__name__}---')
    tasks = []
    for url in urls:
        task = asyncio.create_task(
            func(semaphore, session, url, run_in_executor)
        )
        tasks.append(task)
    logger.info(f'--- Tasks count = {len(tasks)} ---')
    return await asyncio.gather(*tasks)


async def main():
    pool = ThreadPoolExecutor(max_workers=cpu_count())
    loop = asyncio.get_event_loop()
    run_in_executor = partial(loop.run_in_executor, pool)
    semaphore = asyncio.Semaphore(settings.SEMAPHORE_COUNT)

    async with ClientSession() as session:
        urls = await fetch_all_pages_url(session, run_in_executor)
        images_urls = list(
            chain.from_iterable(
                await run_tasks(urls, session, semaphore, fetch_images_urls, run_in_executor)
            ))
        await run_tasks(images_urls, session, semaphore, download_image)


if __name__ == '__main__':
    start_time = time.time()
    logger.info('--- Script has been started. ---')
    try:
        check_dir()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('--- Script has been stopped manually! ---')
    except Exception as e:
        logger.exception(e)
    else:
        logger.info('--- Script has been finished successfully. ---')
    finally:
        logger.info(f'--- Operating time is {time.time() - start_time} seconds. ---')
