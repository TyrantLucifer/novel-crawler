import shutil
import requests
import time
import os
import argparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from multiprocessing import Pool
from tqdm import tqdm

SEARCH_URL = 'https://www.xbiquge.la/modules/article/waps.php'
DOMAIN_URL = 'https://www.xbiquge.la'
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36',
}


def init_parser():
    """
    初始化命令行解析器
    :return: 命令行解析器
    """
    parser = argparse.ArgumentParser(description="A small novel crawler",
                                     epilog='Powered by tyrantlucifer')
    parser.add_argument("-t", "--thread", type=int, default=10, help='the thread num of crawler')
    parser.add_argument("-n", "--name", help='the name of novel')
    parser.add_argument("-a", "--author", help='the name of novel author')
    return parser


def init_browser():
    """
    初始化selenium
    :return: selenium
    """
    chrome_options = Options()
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--ignore-ssl-error')
    chrome_options.add_argument("--ignore-certificate-error")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    browser = webdriver.Chrome(options=chrome_options)
    return browser


def search_novel(novel_name) -> list:
    """
    搜索小说
    :param novel_name: 小说名称
    :return: 搜索结果列表，列表中每个元素为搜索结果的详细信息
    """
    headers = DEFAULT_HEADERS.copy()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    data = {
        'searchkey': novel_name
    }
    http_result = requests.post(SEARCH_URL, headers=headers, data=data)
    http_result.encoding = 'utf-8'
    soup = BeautifulSoup(http_result.text, 'html.parser')
    item_list = soup.find_all(name='tr')
    result_dict_list = list()
    for item in item_list[1:]:
        result_dict = dict()
        contents = item.find_all(name='td')
        result_dict['novel_name'] = str(contents[0].text).strip()
        result_dict['novel_url'] = contents[0].a.get('href')
        result_dict['latest_chapter'] = str(contents[1].text).strip()
        result_dict['author_name'] = str(contents[2].text).strip()
        result_dict['latest_update'] = str(contents[3].text).strip()
        result_dict_list.append(result_dict)
    return result_dict_list


def get_novel(result_dict_list, novel_name, author_name) -> dict:
    """
    从搜索结果中判断是否有指定的结果
    :param result_dict_list: 搜索结果
    :param novel_name: 小说名称
    :param author_name: 作者名称
    :return: 小说详情
    """
    for result_dict in result_dict_list:
        if result_dict['novel_name'] == novel_name and result_dict['author_name'] == author_name:
            return result_dict


def get_novel_chapters(novel_dict) -> list:
    """
    获取小说章节列表
    :param novel_dict: 小说搜索结果
    :return: 小说章节列表
    """
    headers = DEFAULT_HEADERS.copy()
    headers['Referer'] = SEARCH_URL
    novel_url = novel_dict['novel_url']
    http_result = requests.get(novel_url, headers=headers)
    http_result.encoding = 'utf-8'
    soup = BeautifulSoup(http_result.text, 'html.parser')
    div = soup.find(name='div', attrs={'id': 'list'})
    dds = div.find_all(name='dd')
    chapters = list()
    for dd in dds:
        chapter = dict()
        chapter['chapter_url'] = DOMAIN_URL + dd.a.get('href')
        chapter['chapter_name'] = str(dd.text).strip()
        chapters.append(chapter)
    return chapters


def get_chapter_content(browser, chapter) -> str:
    """
    获取章节内容
    :param browser: selenium对象
    :param chapter: 章节信息
    :return: 章节内容
    """
    chapter_url = chapter['chapter_url']
    chapter_name = chapter['chapter_name']
    browser.get(chapter_url)
    time.sleep(0.05)
    div = browser.find_element(By.ID, 'content')
    return '###' + chapter_name + '\n' + div.text + '\n'


def split_list(lst, n):
    """
    根据份数顺序切分一个列表
    :param lst: 要切分的列表
    :param n: 要切的份数
    :return: 一个迭代器
    """
    size, rest = divmod(len(lst), n)
    start = 0
    for i in range(n):
        step = size + 1 if i < rest else size
        stop = start + step
        yield lst[start:stop], i
        start = stop


def execute(chapters, index):
    """
    线程章节爬虫子任务
    :param chapters: 要爬的章节
    :param index: 当前任务索引
    :return: None
    """
    browser = init_browser()
    browser.minimize_window()
    for chapter in tqdm(chapters, desc='thread{0}'.format(index)):
        content = get_chapter_content(browser, chapter)
        with open('novel/{0}.txt'.format(index), 'a+', encoding='utf-8') as file:
            file.write(content)
        # print('{0} 下载完毕~~'.format(chapter['chapter_name']))
        time.sleep(0.5)
    browser.close()


def merge_files(novel_name):
    """
    合并多线程文件
    :param novel_name: 小说名称
    :return: None
    """
    file_dir = os.path.join(os.getcwd(), 'novel')
    files = os.listdir(file_dir)
    novel = open('{0}.txt'.format(novel_name), 'w', encoding='utf-8')
    for i in range(len(files)):
        for line in open(os.path.join(file_dir, '{0}.txt'.format(i)), 'r', encoding='utf-8'):
            novel.writelines(line)
    novel.close()
    shutil.rmtree(file_dir)


def run(thread_num, novel_name, author_name):
    thread_pool = Pool(thread_num)
    novel_dict_list = search_novel(novel_name)
    novel_dict = get_novel(novel_dict_list, novel_name, author_name)
    if novel_dict is not None:
        chapters = get_novel_chapters(novel_dict)
        file_path = os.path.join(os.getcwd(), 'novel')
        if os.path.exists(file_path):
            shutil.rmtree(file_path)
        os.mkdir(file_path)
        [thread_pool.apply_async(execute, args=(chapter, i)) for chapter, i in
         split_list(chapters, thread_num)]
        thread_pool.close()
        thread_pool.join()
        merge_files(novel_name)
    else:
        print("小说不存在~~~")


def main():
    parser = init_parser()
    args = parser.parse_args()
    if args.name and args.author:
        run(args.thread, args.name, args.author)
    else:
        print("args is error, please use it as the following example: python main.py -n 雪鹰领主 -a 我吃西红柿")


if __name__ == "__main__":
    main()
