from twikit import Client, TooManyRequests
import asyncio
from datetime import datetime
import json
from math import ceil
import time, os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate


load_dotenv(override=True)


client = Client('en-US')

client.load_cookies('cookies.json')

unique_usernames = ('inversebrah', 'Markonyx', 'BrianDEvans', 'cryptohayes', 'btc_charlie', 'ninjascalp', 'thecrowtrades', 'theNFTjosh', 'ReticateNFT', 'justinsuntron', 'army_shiba', 'Lthememecoin', 'watanabesota', 'Solana_Emperor', 'gabrochmet', 'bunniefied', 'DannyCrypt', 'emptyholdings', '18decimals', 'LilEthereum', 'lidofinance', 'JumperWave', 'MatthewXBT', 'aaronsniper7', 'mycroftnft', 'stilglobal', 'pierre_crypt0', 'lordproh', 'realMeetKevin', 'Crypto_Hawkk', 'HMsheikh4', 'trader_tim_', 'bx1core', 'mindaoyang', 'burlingtoneth', 'CryptoCred', '0xc06', 'its_airdrop', 'stpaddypirate', 'defyeth', 'satsdart', 'MacLaneWilkison', 'crypto_peet', 'stevewilldoit', 'inmortalcrypto', 'Delphi_Digital', 'anbessa100', 'poe_ether', 'wauwda', 'gorea98', 'crypto_linn', 'zmanian', 'arthur_0x', 'LizzCryptoo', 'JuustinEth', 'hunter_crypto7', 'irish89x', 'sandraaleow', 'RoccobullboTTom', 'coookie137', '0xkyle__', 'TendermintTimmy', 'definapkin', 'jiggadrin_', 'hankhero', 'AntoniNexo', 'jamiekingston', 'CryptoMichNL', '0xDonCrypto', 'Evan_ss6', 'RuneKek', 'KGtradez', '0xSleuth_', 'AureliusBTC', 'memelandsolana', 'DeFi_Cheetah', 'kencharts', 'cryptomanran', 'ritesh_trades', 'ArthurNFTx', 'Kween_eth', 'mark_cullen', 'thecryptocactus', 'cryptowizardd', 'ailseeingeyes', 'reuqz', 'JCBAYC', 'MartaVerse', 'coredotlab', 'gainzy222', 'AviFelman', 'enzcrypto_', 'keoneHD', 'bull_bnb', 'w0lf0fcrypt0', 'abetrade', 'Secured_Fi', 'autumngives', 'chatwithcharles', 'Galois_Capital', 'honey_xbt', 'moomsxxx', 'bgarlinghouse', 'JasCrypto_', 'cryptoninjaah', 'woonomic', 'fraxfinance', 'alejito_eth', 'Blueofweb3', 'apedtop', 'andr3w', '0xPrismatic', 'luckychartape', 'kapothegoat01', 'realdogen', 'traderdaink', 'cryptoambrosio', 'Crypto_Chase', '0xUnihax0r', 'livercoin', 'gvrcalls', 'Tradermayne', 'Kristofer_Sol_', 'infleksif', 'LadyofCrypto1', '0xgrunger', 'KingZedan007', 'zibbaay', 'redactedcartel', 'cryptodonalt', 'ezcharts_', 'suganarium', 'jackzampolin', '0xRyze', 'UxGsol', 'chitaglorya3rd', 'HeiraCrypto', 'tmim87s', 'Injmuncher', 'crypto_scient', 'lsdinmycoffee', 'knveth', 'OxTochi', 'MyFinancialFri', 'wizardofsoho', 'lethal_affu', 'NickNFTn', 'web3_Phil', 'ShazSMM', 'krugermacro', 'donfire666', 'PSCupdates', 'ilxn_NFT', 'C_POTENS', 'richardcraib', 'silverbulletbtc', 'curatedbyromano', 'brucepon', 'TheDeFiPlug', 'bitcoinnhabebee', 'zachxbt', 'NeoVikingsADA', 'defi_paanda', 'DxDmytro', 'iamnickrose', 'zoomerfied', '1tsmeAria', 'ChicoCrypto', 'cryptoWZRD_', 'felixmxu', 'LuckiWeb3', 'IvanOnTech', 'rleshner', 'msjemmagreen', 'jihanicorn', 'gmoneyNFT', 'macrocrg', '0xVKTR', 'eth_rocco', 'NFTGUYY', 'web3ree', 'HumaCapital', 'damskotrades', 'Jef_NfT', 'ApeDurden', 'jammathehamma1', '0xSweep', 'DaoKwonDo', 'VelarBTC', 'sunnya97', 'StaniKulechov', 'jeremy_omgnet', 'defihunter1', 'brcchain_io', 'Tacoio', 'alaskr', 'Echobrc20', 'alexblania', 'maythous', 'incomesharks', 'orangie', 'SatoshiVM', 'kaminocrypto', 'SkyV_KCG', 'webeeu', 'traderkoz', 'JTheDegenn', 'AmeerNFTs', 'arimeilich', 'banescusebi', 'RunnerXBT', 'Nidhal0607', 'ix_wilson', 'AWice', '52kskew', 'Falleraaa', 'RealPabloHeman', 'CryptoWithLeo', 'gavofyork', 'Dehkunle', 'aguilatrades', 'arthurb', 'DaanCrypto', 'cryptogodjohn', 'cryptotickers', 'MortyWeb3', 'pajeetgonzales', 'jimtalbot', 'FlayNFT', 'ivshti', 'bitbenderbrink', 'pwnlord69', 'Defispot', 'OdiCrypt', 'Jake_Nyquist', 'NFTOdettes', 'johncusack', 'RoofHanzo', 'taegiveaway', 'OsmosisCC', 'DrROMAN_NFT', 'roman_trading', 'SneakyGems', 'SolSniffer', 'carv_official', 'sibeleth', 'kieranwarwick', 'cheatcoiner', 'satoshilite', 'hsakatrades', 'NischalShetty', 'drakeondigital', 'ForzaNft', 'realrickschmitz', 'cryptoskullx', 'govanisher', 'CryptoTalkMan', 'RookieXBT', 'GwartyGwart', 'iiamchucky', 'duje_matic', 'demexchange', 'thecryptokazi', 'PedroALPHAA', '0xwushu', 'BringMeCoins', 'Jstn0x', 'ninerealms_cap', 'hyuktrades', 'eliz883', 'neoktrades', 'mrjasonchoi', 'shinigamixbt', 'astekz', 'cryptoshlug', 'VixenNFTs', 'jeetsbyNav', 'N3xusLtd', 'thewolfofdefi', 'addmin_coleen', 'coinsh0t', 'cryptoposeidonn', 'cryptodamus411', 'notEezzy', 'rektproof', 'crypnuevo', 'dweebseth', '0xcarbon', '0xRobbStack', 'pupmos', 'DegensTogether', 'Pentosh1', 'snshantal', 'cupcakeoce', 'dcfgod', 'breakoutprop', 'bramcohen', 'bigcheds', 'cxrtezwrld', 'O_H_JAY', 'legitinfluencer', 'KeithWoodsYT', 'giba_machado', 'quantmeta', 'StackerSatoshi', 'roneilr', 'hc_trades', 'Lightspeedpodhq', 'ryanzarick', 'alpha_pls', 'elontrades', 'mr_pschmitt', 'barkmeta', 'shytoshikusama', 'cryptonazer', 'spidercrypto0x', 'cryptopeltz', 'resdegen', 'tareeq_23', 'Ghostt_Nft', 'blockgraze', 'JJ_NFTx', 'papa_woody21', 'SWHEATZ1', 'larry0x', 'ledgerstatus', 'crypttorebel', 'Ayden_eth', 'DogeGirl420', 'cryptothannos', 'haydenzadams', 'DJ_GIVEAWAY2', 'cryptofvcker', 'cryptoo_alice', '0x_charlemagne', 'normfinkelstein', 'BenYorke', 'ericcryptoman', 'RockyPocky123', 'ManLyNFT', 'alexmaxth0r', 'rush_hour51', 'astrologycrypto', 'spadaboom1', 'ZGodegen', 'Ucan_Coin', 'cremedelacrypto', 'thorshammergems', 'pythianism', 'defi_maestro', 'BobGaine', 'lilmoonlambo', 'JusticeJB_', 'FerreNFT', 'kceeonyekachi1', 'autholykos', '0xdai2', 'zee_maker', 'crypto_condom', 'trader1sz', 'ColdBloodShill', 'cryptojimsgems', '0xxghost', 'defi_mochi', 'TurkishGiveaway', 'suji_yan', 'CryptoVikings07', 'JohnyCrypto', 'BowtiedPyro', 'nnevvinn', 'schrotti77', 'Ebubechi_GMI', 'xTheTechZz', 'saiyancrypt0', 'TimDraper', 'gemsofra', 'CryptoPunjab09', 'Zeneca', 'nomichef', 'scupytrooples', '9gagceo', 'blocmatesdotcom', 'thormaximalist', 'CryptoZeusYT', '1CryptoWolves', 'SalsaTekila', 'KazTheShadow', 'Lebearsol', 'rogerkver', 'goobygambles', '0x366e', 'jamesmcdegen', 'Tama_BMCM', 'deacix', '_krishnagori', 'CumberlandSays', 'EvanLuthra', 'O_0xEther', 'thecryptoles', 'blocksnthoughts', 'SeiParrots', 'WisdomMatic', 'deseventral', 'orionparrott', 'DayanaCrypto', 'teddi_speaks', 'TeachersPetNFT', 'NachoTrades', 'robert_lauko', 'limitlessbur', 'EleanorTerrett', '_BillionAireSon', 'Cryptocito', 'coinmamba', 'crayola_capital', 'HarrisCrypto0', 'ZeMariaMacedo', 'born2hodl', 'umitanuki', 'yourfriendsli', 'Abrahamchase09', 'sizeab1e', 'angelobtc', 'Awawat_Trades', 'RickLFG', 'wtfrzv', 'fernosampaio', 'defiminty', 'poopmandefi', 'donwinning1', 'mzhao8', 'voidputs', 'lomahcrypto', 'johnnybtrader', 'fungialpha', 'offshoda', 'script_network', 'Darrenlautf', '0mniscientus', 'astroport_fi', 'SatoshiLite', 'Web3Pikachu', 'themarcojo', 'Lowkey0nline', 'crypto_inez', 'AndrewChoi5', 'missauris3', '999wrldkris', 'EarnAirdrop', 'degenlifer', 'cryptomorgz', 'boatnudlez', 'bob_baxley', '1MillSaviour', '0xJoash', 'chirocrypto', 'cryptokaduna', 'iSmeshCrypto', 'buchmanster', 'bcecil', 'jinglejamop', 'MacnBTC', 'Pure8Nature', 'BATMAN_png', 'mars_protocol', 'daniei_loopring', 'jkrdoc', 'wilsonwei777', 'obitocrypt0', '0xhedge32', 'cryptopainzy', 'LullabyWeb3', 'BlancPixels', 'CenkCrypto', 'icedknife', 'JUNEO_official', 'JustZik', 'solana_king', 'Shaughnessy119', 'el__mag0', 'iambroots', 'allgiveawaysda1', 'e_schhneider', 'VitalikButerin', 'trungfinity', 'nittai1963', 'JamieThomsonVF', 'jonzitrades', 'deltaxbt', 'princesspromos_', 'aniket_jindal08', 'frensvalidator', 'MariusCrypt0', 'loi_luu', 'tonymoontanaeth', 'SamuelXeus', '1CryptoMama', '0xbispo', 'curiousnise', 'EduRio_', 'criptopaul', '3games2023', 'davexbt97', 'PrudentSammy', '0xMert_', 'Ambush', 'bullrun_gravano', 'zssbecker', 'deebs_defi', 'pclaudius', 'gotzeuus', 'LeonHuobi', 'abrkn', 'EclipseFND', 'artsch00lreject', 'hosseeb', 'cz_binance', 'nft_cryptogang', 'liquidlizard_', 'michaelfkong', 'JustBluishxD', 'saliencexbt', 'CryptoTechDAO', 'henripihkala', 'cometcalls', 'cryptodefilord', 'trueEarth_pilot', 'alexwearn', 'Lulubnbvip', 'NFTNURI', 'PC_PR1NCIPAL', 'dacryptogeneral', 'milky_way_zone', 'GemsScope', 'theapeterminal', '3jack23', 'ssrinawakoon', 'MOLYA_crypto', 'RoarWeb3', 'Call_Me_Kael', 'ganymede_0x', 'thedefiedge', 'gabusch', 'antoniomjuliano', 'CryptoXPromo', 'Cryptobullmaker', 'wacy_time1', 'dropslemons', 'CryptoWisdom9', 'leonardnftpage', 'NftDaki', 'risiah1', 'lawlietcrypto', 'sergeynazarov', 'HerroCrypto', 'M78_club', 'zbruceli', 'marshallhayner', 'doerxbt', 'edisonlabz', 'MitoFinance', 'defi0xjeff', 'sanjakon', 'pacmanblur', 'bullchain', 'shib__whales', 'OmniTradeA1', 'gametheorizing', 'koeppelmann', 'emperorbtc', 'Legal0insurance', 'farmerfrens', 'Matt_Furie', 'commiehat', 'ey_pablo', 'george1trader', 'rainascrd', 'pepesolana_pepe', 'IzNoGooDNFT_', 'jarxiao', 'bloomstarbms', 'crypto_TomTom', 'insects_wtf', 'kelty_nft', 'overdose_ai', 'nikil', 'willwarren', 'ArowNFT', 'altcoinsherpa', 'Klekshun', 'defiwizzy', 'bloodgoodbtc', 'smokethatdank1', 'chadcaff', 'Curionic', 'ilblackdragon', 'defiignas', 'sojuuxv', 'rektcapital', 'vostracrypto', 'devchart', 'coingurruu', 'Totinhiiio', 'gandalfthebr0wn', 'ovedm606', 'aeyakovenko', 'Hawko_44', '0xpibblez', 'crypto_ideology', 'patex_ecosystem', 'ali_charts', 'nate_rivers', 'cryptogirlnova', 'CryptoGemRnld', 'jtradestar', 'kazonomics', 'mick_contentos', 'saint_pump', 'bhaleyart', 'MetisDAO', 'solbigbrain', 'tier10k', 'rektdiomedes', 'giveawaywoman', 'thedefinvestor', 'EveyNFT', 'vitalikbuterin', 'shitc0in', 'cryptocevo', 'neon___glow', 'fitforcrypto_', 'WallStreetSilv', 'pepe_wtf_eth', 'bitcoinhabebe', 'kingpincrypto12', 'TheMagicAff', 'crypto_aeon7', 'Basesol_NFT', '_ambigramm', 'littlemustacho', 'sirgmi', 'conorfkenny', 'Banks', 'jacknuked', 'trader_koala', '4JusticeWeb3', 'Khaled_winner', '90BE90', 'robw00ds', 'ethereumJoseph', 'WOLF_WebThree', 'AcaPromos', 'TweetByWale', 'MantaNetwork', 'cryptotribe_in', 'KoroushAK', 'zachonsolana', 'shahafbg', 'bengoertzel', 'MINGJUNBJ', 'Joshyysmartt', 'playbuxco', 'Noahhweb3', 'Ashcryptoreal', 'crypthoem', '4500px', 'viktordefi', 'cryptokoryo', 'newmichwill', 'odododod69', 'naniXBT', 'yanivgraph', 'scampcoin', 'palletjacker69', 'andrecronjetech', 'crypto_scar', 'simonyusea', 'NateGeraci', 'jfurgo', 'vikmeup', 'ibcig', 'EnigmaValidator', 'IboGoez', 'ryanrrs', 'bradherenow', 'JukeNFT', 'petkanics', 'sell9000', 'AltcoinPsycho', 'kaiynne', 'SharkyWeb3', '0xfitz', 'nicksdjohnson', 'OndoFinance', 'borgetsebastien', 'bagcalls', 'CryptoKaleo', 'MrCustomSuit', 'XMaximist', 'blockchain_mane', 'murocrypto', 'BarrySilbert', 'kenwgmi', 'MagicSquareio', 'zibin', 'OpSecCloud', 'TheTreeverse', 'Sheldon_Sniper', 'CryptoShillz06', 'hbj_trades', 'Project_TXA', '0xandrewmoh', 'astral_eth_92', 'djqianfusion', 'cryptorezeh', 'crypto_mckenna', 'razvantrades', 'corey_ape', 'semperveritas0', 'ShinyNfts', 'sus_ape', 'follis_', 'kongbtc', 'Mr_Raymondx', 'GCRClassic', 'Eunicedwong', 'moemaxi_', 'richapez', 'blockchainedbb', 'DarkCryptoLord', 'louround_', 'CryptoEmree_', 'EricBalchunas', 'tradernj1', 'WWTLitee', 'Finch_in_flight', 'VirtualBacon0x', 'numerooo0', 'SoulzBTC', '0xtindorr', '0xFuturNFT', 'DoubleDownNews', 'CharlotteNftArt', '___jackals', 'middlechildpabk', 'cryptoboss2000', 'sisca_crypto', 'patty_fi', 'sgoldfed', 'JIOVERSE', 'mhdksafa', 'cameron', 'Cabanaandre1', 'reetikatrades', 'joegrower420', 'el33th4xor', 'parabolit', 'gverdian', 'VictorAfaka', 'semangast', 'en_k_ts', 'SatoshiFlipper', 'MattInWeb3', 'crosschainalex', 'stake_mm', 'taeboukie', 'CoineraKV', 'dak_flux', 'Kucoinmaster777', 'Goran_Crypto', '0xcygaar', 'melynx', 'bmescrypto', 'ClareDalyMEP', 'Maymytan', 'ivan_switcheo', 'murtazasats', 'Protectoratexyz', 'bxrcrypto', 'qc_qizhou', 'IamNomad', 'RAFAELA_RIGO_', 'Dojo_Swap', 'jon_charb', 'Freemanwastaken', 'egirl_capital', '0xPolygonApe', 'ceterispar1bus', 'drprofitcrypto', 'sandeepnailwal', 'BlockChain_CK', 'coderdannn', 'art_xbt', 'mbeNFT', 'alanchiu', 'jasonpizzino', 'bitbitcrypto', 'BlankBrainTrade', 'scar_crypto', 'FatManTerra', 'crypto_bitlord7', '__bleeker', 'milesdeutscher', 'ZeroXSaitama', 'cryptotony__', 'brendaneich', 'DegenSpartan', 'chilltrd', 'owocki', 'CWEmbassy', 'erickdemoura', 'oz_wuu', 'NFTLucas_', 'RealMiguelMorel', 'joshfraser', '0xferg', 'ericinjective', 'CryptoMafia06', 'daysonkick', 'wsbmod', 'K9_Crypt0', 'TJFX98')


DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')
DATABASE_NAME_EMBEDDINGS = os.getenv('DATABASE_NAME_EMBEDDINGS')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PGVECTOR_CONNECTION_STRING = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME_EMBEDDINGS}"
persist_directory = 'cryptobuzz_testing'


async def next_search(tweets, query):
    if tweets is None:
        tweets = await client.search_tweet(query, 'Latest')
    else:
        tweets = await tweets.next()
    
    return tweets


embedding_model = OpenAIEmbeddings()


async def search_tw(start_date, end_date):
    try:
        with open("tweets.json", "r") as json_file:
            existing_data = json.load(json_file)
    except FileNotFoundError:
        existing_data = {}

    qcount = 1
    count = 1

    for i in range(ceil(len(unique_usernames) / 10)):
        user_list = unique_usernames[i * 10 : i * 10 + 10]
        query = ""
        for c, user in enumerate(user_list):
            if c == 0:
                query += f"(from:{user} "
            else:
                query += f"OR from:{user} "

        query = query.strip() + f")until:{end_date} since:{start_date}"
        print("Query = ", query)
        print("Query count =", qcount)

        qcount += 1

        tweets = None

        while True:
            try:
                tweets = await next_search(tweets, query)
            except Exception as e:
                print(f"Exception while fetching tweets: {e}")
                if hasattr(e, "rate_limit_reset"):
                    rate_limit = datetime.fromtimestamp(e.rate_limit_reset)
                    wait_time = rate_limit - datetime.now()
                    print(f"Rate limit exceeded, retrying in {wait_time}, {rate_limit}")
                    await asyncio.sleep(wait_time.total_seconds())
                    continue
                else:
                    print("Different Exception = ", e)
                    continue

            if not tweets:
                print("No more tweets to fetch")
                break

            past_data = False
            documents = []

            for tweet in tweets:
                check_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                tw_date = tweet.created_at_datetime.date()

                if check_date > tw_date:
                    past_data = True
                    break

                print(f"Processing tweet {count}")
                count += 1
                username = tweet.user.screen_name
                tweet_data = {
                    "content": tweet.full_text.strip(),
                    "date": tweet.created_at_datetime.isoformat(),
                }
                print(
                    f"username = {tweet.user.screen_name}\ntweet = {tweet.full_text}\ndate = {tweet.created_at_datetime}\nconverted date = {tweet.created_at_datetime.isoformat()}"
                )

                if username in existing_data:
                    user_data = existing_data[username]
                    if tweet.id not in user_data["tweets"]:
                        user_data["tweets"][tweet.id] = tweet_data
                        print(f"Added new tweet for {username}")
                    else:
                        user_data["tweets"][tweet.id]["content"] = tweet_data["content"]
                        user_data["tweets"][tweet.id]["date"] = tweet_data["date"]
                else:
                    existing_data[username] = {
                        "tweets": {tweet.id: tweet_data}
                    }

                # Create document for embedding
                documents.append(
                    Document(
                        page_content=tweet.full_text.strip(),
                        metadata={
                            "tweet_id": str(tweet.id),
                            "username": username,
                            "date": tweet.created_at_datetime.isoformat(),
                        }
                    )
                )

                with open("tweets.json", "w") as json_file:
                    json.dump(existing_data, json_file, indent=4)

            # Generate embeddings and store with metadata
            if documents:
                try:
                    # Use embed_documents method to generate embeddings
                    # embeddings = embedding_model.embed_documents([doc.page_content for doc in documents])

                    PGVector.from_documents(
                        documents=documents,
                        embedding=embedding_model,
                        collection_name=persist_directory,
                        connection_string=PGVECTOR_CONNECTION_STRING,
                        use_jsonb=True,
                    )
                    print(f"Successfully stored {len(documents)} embeddings in vector store.")
                except Exception as e:
                    print(f"Error storing embeddings: {e}")

            if past_data:
                print("breaking the loop bcoz of previous date")
                break

      
def create_prompt_template():
    custom_prompt_template = """
        You are CryptoInsightBot, an advanced AI assistant designed to analyze and summarize cryptocurrency-related tweets. Your primary task is to extract actionable insights, provide accurate answers, and identify market sentiment based on tweets from cryptocurrency influencers and enthusiasts.
        user's query: {question}
        And here is the database of tweets to analyze: {context}

        When responding to user queries:

        Refer to the tweets in your database and extract relevant information. Include the tweet content, user name, and date in your response for context.
        Analyze the sentiment of the tweets (bullish, bearish, or neutral) and summarize the tone of the market when relevant.
        Provide clear and actionable investment recommendations based on the tone, content, and context of the tweets.
        When appropriate, explain trends or key topics (e.g., Bitcoin price predictions, Ethereum ecosystem growth) mentioned in the tweets to help users make informed decisions.
        Always strive to offer insightful, data-driven answers that empower the user to make sound investment or trading decisions. Tailor your tone to be professional, accurate, and concise.
        """

    input_variables = ["context", "question"]

    prompt = PromptTemplate(
        template=custom_prompt_template, input_variables=input_variables
    )
    return prompt


def retrieval_qa_chain():
    prompt = create_prompt_template()

    embedding = OpenAIEmbeddings()
    llm = ChatOpenAI(model="gpt-4o", temperature=0.5)

    vector_store = PGVector(
        connection_string=PGVECTOR_CONNECTION_STRING,
        collection_name=persist_directory,
        embedding_function=embedding,
        use_jsonb=True
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": 8})
    #working code 
    # retriever = vector_store.as_retriever(
    #     search_kwargs={
    #         "k": 8,
    #         "filter": {"username": "TheCrowtrades"}}
    #     )
    #------------------------------
    # retriever = vector_store.as_retriever(
    #     search_kwargs={
    #         "k": 8,
    #         "filter": {"cmetadata": {"username": {"$in": "btc_charlie"}}}
    #     }
    # )
    print(retriever,'************************')
    chain = RetrievalQA.from_llm(
        llm=llm,
        return_source_documents=True,
        retriever=retriever,
        prompt=prompt,
    )
    return chain


def run_retrieval_chain(chain, query, chat_history=None):

    result = chain.invoke(query)

    answer = result["result"]

    return {
        "answer": answer,
    }


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(search_tw(start_date="2024-12-04", end_date="2024-12-05"))
    print("\n--- %s seconds ---" % (time.time() - start_time))

    chain = retrieval_qa_chain()

    user_query = "What are the tweets of TheCrowtrades?"

    result = run_retrieval_chain(chain, query=user_query)

    print("Answer:", result["answer"])