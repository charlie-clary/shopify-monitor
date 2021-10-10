import requests
import logging
import json
from threading import Thread
import time
from discord_webhook import DiscordWebhook, DiscordEmbed
import sys
import random

headers = {
    'Accept-Language': 'en-US,en;q=0.9',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
}

logging.basicConfig(
    level=logging.INFO,
    format="{asctime} {levelname:<8} {message}",
    style="{",
    filename="mylog.log",
    filemode="w"
)


def getConfig():
    try:
        logging.info("getting config info")
        f = open('config.json', 'r')
        data = json.load(f)
        return data['filteredHook'], data['unfilteredHook'], data['filteredActive'], data['keywords'], data['monitorDelay'], data['errorDelay']
    except:
        logging.critical("NO CONFIG FILE EXISTS, EXITING PROGRAM")
        sys.exit("EXITING PROGRAM")


def getSites():
    try:
        logging.info("getting sitelist")
        return open('sites.txt', 'r').read().splitlines()
    except:
        logging.error("SITELIST FILE DOES NOT EXIST OR IS EMPTY EXITING PROGRAM")
        sys.exit("EXITING PROGRAM")


sites = getSites()
filteredhook, unfilteredhook, filteredactive, keywords, monitordelay, errordelay = getConfig()
stockArr = []


def getProxy():
    try:
        proxies = open('proxies.txt', 'r').read().splitlines()
        rand = random.choice(proxies)
        split = rand.split(':')
        if isUserPass(rand):
            ip, port, user, password = split[0], split[1], split[2], split[3]
            return {'https': 'http://' + '{0}:{1}@{2}:{3}'.format(user, password, ip, port)}
        ip, port = split[0], split[1]
        return {'https': 'http://' + '{0}:{1}'.format(ip, port)}

    except Exception as e:
        logging.critical("ERROR GETTING PROXY, EXITING PROGRAM")
        logging.critical(str(e))
        sys.exit("EXITING PROGRAM")


def isUserPass(proxy):
    if len(proxy.split(':')) == 4:
        return True,
    return False


def getProdInfo(prod):
    try:
        title = prod['title']
    except:
        title = "Default Title"
    try:
        price = prod['variants'][0]['price']
    except:
        price = "Default Price"
    try:
        img = prod['images'][0]['src']
    except:
        img = "https://cdn.discordapp.com/attachments/698993102697791581/853425706939449374/download.png"
    return title, price, img


def postToDiscord(url, site, title, price, img, variants):
    try:
        webhook = DiscordWebhook(url=unfilteredhook)

        if any(keyword in title for keyword in keywords) and filteredactive:
            webhook = DiscordWebhook(url=filteredhook)
            logging.info("keyword in title, posting to filtered hook")

        embed = DiscordEmbed(color=16765905, title=title)
        embed.set_footer(text='chuckerz shopify',
                         icon_url='https://cdn.discordapp.com/attachments/698993102697791581/780852023302029342/chuckerz_logo.png')
        embed.set_thumbnail(
            url=img)
        embed.set_timestamp()
        embed.add_embed_field(name='Link',
                              value='[URL]({0})'.format(url),
                              inline=True)

        embed.add_embed_field(name='Price',
                              value="$" + str(price), inline=True)

        embed.add_embed_field(name='Site',
                              value=str(site), inline=True)

        embed.add_embed_field(name='Sizes',
                              value=str(variants), inline=True)

        webhook.add_embed(embed)
        r = webhook.execute()
        if ('rate limited' in r.text):
            logging.error("discord rate limit, sleeping 10s and retrying...")
            time.sleep(10)
            postToDiscord(url, site, title, price, img, variants)
    except Exception as e:
        logging.critical("Error occured posting to discord " + str(e))


def getInfo(prod, site):
    try:
        handle = prod['handle']
        prodUrl = 'https://{0}/products/{1}'.format(site, handle)
        variants = prod['variants']
        stock = False
        for v in variants:
            if (v['available'] == True):
                stock = True
        return prodUrl, stock
    except Exception as e:
        logging.error("Error getting product info")
        logging.error(str(e))


def getVariants(prod, site):
    try:
        variants = []
        for v in prod['variants']:
            if v['available']:
                format = str("[{0}]({1})".format(str(v['title']), "https://{0}/cart/{1}:1".format(site, v['id'])))
                variants.append(format)
        return '\n'.join(variants)
    except Exception as e:
        logging.error("Error getting variant info")
        logging.error(str(e))
        return None



def getInitList():
    logging.info("logging initial products")
    for site in sites:
        try:
            proxy = getProxy()
            logging.info("logging initial products on " + site + " with proxy " + str(proxy))
            r = requests.get('https://{0}/products.json?from=135297231&to=2035543867467'.format(site), headers=headers, proxies=proxy)
            a = json.loads(r.text)
            for prod in a['products']:
                try:
                    prodUrl, stock = getInfo(prod, site)
                    prodArr = [prodUrl, False]
                    stockArr.append(prodArr)
                except Exception as e:
                    logging.error(
                        "Error logging product on " + site + "sleeping " + str(errordelay) + " seconds")
                    logging.error(str(e))
        except Exception as e:
            logging.error("Error logging initial products on " + site + " sleeping " + str(errordelay) + " seconds")
            logging.error(str(e))
    return stockArr


def monitor(site):
    while True:
        time.sleep(monitordelay)
        try:
            proxy = getProxy()
            logging.info("checking for changes on " + site + " with proxy " + str(proxy))
            r = requests.get('https://{0}/products.json?from=135297231&to=2035543867467'.format(site), headers=headers, proxies=proxy)
            a = json.loads(r.text)
            for prod in a['products']:
                try:
                    prodUrl, stock = getInfo(prod, site)
                    prodArr = [prodUrl, stock]
                    if prodArr not in stockArr:
                        logging.info("change made to " + prodUrl)
                        inStockArr = [prodUrl, True]
                        outStockArr = [prodUrl, False]
                        if inStockArr not in stockArr and outStockArr not in stockArr:
                            logging.info(
                                "new product {0} posted to {1}, posting to discord and adding to stocklist".format(prodUrl,
                                                                                                                   site))
                            stockArr.append(prodArr)
                            title, price, img = getProdInfo(prod)
                            variants = getVariants(prod, site)
                            postToDiscord(prodUrl, site, title, price, img, variants)
                        else:
                            if prodArr[1] == False:
                                logging.info("{0} has gone oos, updating stocklist".format(prodUrl))
                                index = stockArr.index(inStockArr)
                                stockArr[index] = prodArr
                            else:
                                logging.info("{0} has restocked, posting to discord and updating stocklist".format(prodUrl))
                                index = stockArr.index(outStockArr)
                                stockArr[index] = prodArr
                                title, price, img = getProdInfo(prod)
                                variants = getVariants(prod, site)
                                postToDiscord(prodUrl, site, title, price, img, variants)

                except Exception as e:
                    logging.error("Error parsing products on " + site + "sleeping " + str(errordelay) + " seconds")
                    logging.error(str(e))
                    time.sleep(errordelay)

        except Exception as e:
                logging.error("Error monitoring on " + site + "sleeping " + str(errordelay) + " seconds")
                logging.error(str(e))
                time.sleep(errordelay)

getInitList()
for site in sites:
    frontend = Thread(target=monitor, args=(site,))
    frontend.start()
