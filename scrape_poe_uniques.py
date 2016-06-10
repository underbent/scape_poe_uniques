#! python3
# -*- coding: utf-8 -*-
"""
# scrape_poe_uniques.py - scrapes poe uniques from http://pathofexile.gamepedia.com/Unique_item#UniqueItemTypes
and then writes them, in their category, one per line.
"""

import requests, bs4, re, datetime, time
from bs4 import NavigableString
from multiprocessing.dummy import Pool as ThreadPool


main_url = 'http://pathofexile.gamepedia.com/Unique_item#UniqueItemTypes'

rx_search = re.compile(r'\+*\(([\d\.]+)\s[a-z]+\s([\d\.]+)[)]|(\+*[\d\.]+\%)|([\d\.]+-[\d\.]+)|(\([\d\.]+-[\d\.]+)\s\w+\s([\d\.]+-[\d\.]+\))|(-?\+?[\d\.]+)')
unicode = re.compile(r'[^\x00-\x7F]+')  # regex that can be used to check for unicode chars in text


def build_variant(line):
    """
    Builds the wording in the data dealing with the variants in certain unique items. Doryani's Belt is 1 example
    :param line: str
    :return: str
    """
    var_reg = re.compile(r'(variant.*)')  # regex matches 'variant' and anything after..for removal via .sub()
    x = var_reg.sub('', line).strip()
    x = '| -' + x + '- '
    return x


def build_double_num(data):
    """
    this function is meant for situations where more than one number set is found
    ie: 150-200 to 250-300
    :param data: list
    :return: string
    """
    count = 1
    for num in data:
        if num is not None:
            if count == 1:
                hold_num = num.replace('%', '').replace('+', '').replace('(', '')
                count += 1
            else:
                hold_num += ',' + num.replace('%', '').replace('+', '').replace(')', '')
    hold_num += ':'
    return hold_num


def build_number_data(data):
    """
    builds the number(s) needed for AHK
    :param data: list
    :return: str
    """
    count = 1
    if len(data) >= 6 and data[5] is not None:
        return build_double_num(data)
    for num in data:
        if num is not None:
            if count == 1:
                hold_num = num.replace('%', '').replace('+', '')
                count += 1
            else:
                hold_num += '-' + num.replace('%', '').replace('+', '')
                count += 1
    hold_num += ':'
    return hold_num


def write_file_headers():
    """
    info headers for Uniques.txt

    :return: list
    """
    data = []
    d = datetime.datetime.now()
    now_time = d.strftime('%Y-%m-%d at %H:%M:%S')
    data.append('; Data from http://pathofexile.gamepedia.com/List_of_unique_items')
    data.append('; The "@" symbol marks a mod as implicit. This means a seperator line will be appended after this mod. If there are multiple implicit mods, mark the last one in line.')
    data.append('; Comments can be made with ";", blank lines will be ignored.')
    data.append(';')
    data.append('; This file was auto-generated by scrape_poe_uniquesOriginal.py on {}'.format(now_time))
    data.append('\n')

    return data


def get_main_page(url):
    """
    Gets the main wiki page for Uniques and parses out the links
    for the sub categories and returns a list of the urls
    :param url: main page url
    :return: list of urls
    """
    sub_category_url = []
    print('Getting Web page....')
    page = requests.get(url)
    page.raise_for_status()
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    links_table = soup.find_all('table')  # get tables in page, table[0] contains links
    for category in links_table[0].find_all('div', class_='hlist'):  # each category's links
        sub_category_url.extend(get_category_url(category))  # send to function to get list of links
    sub_category_url.append('http://pathofexile.gamepedia.com/List_of_unique_jewels')  # since there are no sub-categories
    sub_category_url.append('http://pathofexile.gamepedia.com/List_of_unique_maps')  # these links aren't returned, so add them

    return sub_category_url


def get_category_url(data):  # extracts links from the category
    url_list = []
    page_url = 'http://pathofexile.gamepedia.com'
    for elem in data.find_all('a'):
        url_list.append(page_url + elem.attrs['href'])

    return url_list


def get_extra_item_data(data):
    """
    When a Unique item has a <Style Variant>, this function gets the web page with
    the relevant info
    :param data: BS4 object
    :return: list
    """
    unique_data = []
    url = 'http://pathofexile.gamepedia.com' + data.attrs['href']
    print('Getting Web page....')
    page = requests.get(url)
    page.raise_for_status()
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    first_hit = soup.find('span', id='Modifiers')
    found = False
    for next_elem in first_hit.next_elements:  # we need to Navigate the tree here
        if next_elem.name == 'h2':  # when we reach this tag, we are done, break
            break
        if next_elem.name == 'ul':  # this tag contains the variant
            unique_data.append(next_elem.text)
            found = False
        if not found and next_elem.name == 'dl':  # this tag's text has all the variants data, separated by \n
            unique_data.extend(next_elem.text.split('\n'))
            found = True
    return unique_data



def has_id(id):
    """
    a function used for searching a BS4 object. In this case, all Uniques are contained
    in a <tr> element, and only those elements that contain an 'id=' are the valid ones
    basically returns True if there is an id= which tells soup to grab the element
    :param id:
    :return:
    """
    return id is not None


def parse_category_data(link):
    """
    gets the links for all the unique categories and then sends them to build_data()
    to crawl thru and get data for each item
    :param links:
    :return:
    """
    all_data = []
    #for link in links:
    print('Getting Web page...')
    page = requests.get(link)
    page.raise_for_status()
    soup = bs4.BeautifulSoup(page.text, 'html.parser')
    x = build_data(soup.find_all('tr', id=has_id))  # gets the list of Unique Elements (see func has_id)
    all_data.extend(x)

    return all_data


def build_data(data):
    """
    take a BS4 ResultSet of the Unique's category and build a list containing each unique
    and it's implicit (if it exists) and the data.
    The str.replace() done is an attempt to convert some unicode chars found in the data.
    :param data: BS4 ResultSet
    :return: list
    """
    unique_data = []
    all_data = []
    for tags in data:
        tag_content = tags.contents[0].text.rstrip().replace(u'\u00F6', 'o')  # Replace ö with o
        unique_data.append(tag_content)  # name of Unique
        print('Getting data for {}'.format(tag_content))
        for stats in tags.find_all('div', class_='item-stats'):
            if len(stats.contents) == 1:  # unique has no implicit
                pass
            else:
                unique_data.append('@' + stats.contents[0].text)  # the implicit
            for stat in stats.contents[len(stats.contents) - 1].contents:
                try:  # this code searches for uniques like Drillneck that for some reason are different in
                    if len(stat.contents) > 1:  # how they are set on the webpage.
                        for line in stat.contents:
                            if isinstance(line, NavigableString):
                                unique_data.append(str(line).replace(u'\u2212', '-').replace(u'\u2013', '-'))
                except AttributeError:
                    if stat == '<Style Variant> ':  # another web page needs to be gotten
                        x = get_extra_item_data(stats.find('a'))
                        for line in x:
                            unique_data.append(line.replace(u'\u2212', '-').replace(u'\u2013', '-'))
                    if isinstance(stat, NavigableString):
                        unique_data.append(str(stat).replace(u'\u2212', '-').replace(u'\u2013', '-'))
        all_data.append(unique_data)
        unique_data = []

    return all_data


def convert_data_to_AHK_readable_format(all_data):
    """
    This function takes the raw web page data, and converts it into lines that are readable by the
    Poe_item_info AHK script.
    :return:
    """
    new_data = []
    for line in all_data:  # this is the list which contains the item's data
        for list1 in line:  # this iters thru the list and uses regex to search each string
            line_hold = []
            for data in list1:
                data = data.strip()  # trims any leading/trailing whitespace
                data = data.replace(u'\u2013', '-')  # needs another unicode replace sometimes
                mo = rx_search.search(data)  # search with regex and put the results into groups for later editing
                if mo is not None:  # if regex doesn't return a result, usually the item name, or text in item
                    str_hold = rx_search.sub('', data).strip()  # this removes the search result from the string
                    hold = build_number_data(mo.groups())  # sends the search result to be built into AHK readable
                    if '@' in str_hold:  # this is the implicit
                        hold = '@' + hold
                        str_hold = str_hold.replace('@', '')
                    data = '|' + hold + str_hold.strip().title()  # trims and capitalizes the newly constructed string
                    data = data.replace('  ', ' ').replace('% ', '').replace('( To )', '').replace('+', '')  # further cleans up some returned strings
                    line_hold += data  # adds the newly made piece of data to the overall string to be handed back later
                    continue
                if 'variant' in data:  # check the data piece for the variant that needs some special editing.
                    line_hold += build_variant(data)
                    continue
                if len(line_hold) > 0 and data is not '':  # this is for lines that don't have numbers in them, but need to be added
                    data = '|' + data.strip().title()  # to the item's data. designed to catch odds and ends.
                line_hold.append(data)
            new_data.append(''.join(line_hold))  # we've rebuilt the unique's info, so add it to the new list for storage.

    return new_data


def write(new_data):

    file = open('Uniques.txt', 'a')  # opens file for writing
    for row in new_data:
        file.write(row + '\n')  # write each line
    file.close()


def main():
    links_list = get_main_page(main_url)
    open('Uniques.txt', 'w').close()  # create file (or overwrite it if it exists)
    write(write_file_headers())
    pool = ThreadPool(4)  # multi threading! yay
    data = pool.map(parse_category_data, links_list)  # pool.map() threads getting data from links
    x = convert_data_to_AHK_readable_format(data)
    write(x)
    pool.close()  # bookkeeping link
    pool.join()  # bookkeeping link

startTime = datetime.datetime.now()
main()
print('Program execution time: ',(datetime.datetime.now() - startTime))
