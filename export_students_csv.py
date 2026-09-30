import csv
import random

# 学科・コース・クラスの定義
CLASSES_POOL = [
    ('国際アニメーション学科', '作画コース', 'A組'),
    ('国際アニメーション学科', '作画コース', 'B組'),
    ('国際アニメーション学科', 'CGコース', 'A組'),
    ('国際アニメーション学科', 'CGコース', 'B組'),
    ('ゲームクリエイター学科', 'プログラミングコース', '1組'),
    ('ゲームクリエイター学科', 'プログラミングコース', '2組'),
    ('ゲームクリエイター学科', '企画コース', '1組'),
    ('ゲームクリエイター学科', '企画コース', '2組'),
    ('情報IT学科', 'Webシステムコース', 'IT1'),
    ('情報IT学科', 'Webシステムコース', 'IT2'),
    ('情報IT学科', 'DXビジネスコース', 'IT1'),
    ('情報IT学科', 'DXビジネスコース', 'IT2'),
]

# 各国籍の豊富な名前プール（重複が起きないよう200名超のバリエーションを確保）
# 形式: (氏名, フリガナ, ニックネーム, 国籍)
UNIQUE_NAMES = [
    # ベトナム
    ('NGUYEN VAN TUAN', 'グエン ヴァン トゥアン', 'トゥアン', 'ベトナム'),
    ('TRAN THI MAI', 'ﾄﾗﾝ ﾃｨ ﾏｲ', 'マイ', 'ベトナム'),
    ('LE VAN LOC', 'レ ヴァン ロック', 'ロック', 'ベトナム'),
    ('PHAM THI HOA', 'ﾌｧﾑ ﾃｨ ﾎｱ', 'ホア', 'ベトナム'),
    ('BUI QUOC AN', 'ブイ クオック アン', 'アン', 'ベトナム'),
    ('DANG THI LAN', 'ﾀﾞﾝ ﾃｨ ﾗﾝ', 'ランちゃん', 'ベトナム'),
    ('HOANG MINH DUC', 'ホアン ミン ドゥック', 'ドゥック', 'ベトナム'),
    ('VU THI HUONG', 'ヴー ティ フオン', 'フオン', 'ベトナム'),
    ('DOAN VAN HIEU', 'ドアン ヴァン ヒエウ', 'ヒエウ', 'ベトナム'),
    ('NGO QUANG HAI', 'ンゴ クアン ハイ', 'ハイ', 'ベトナム'),
    ('DUONG THI NGOC', 'ズオン ティ ゴック', 'ゴック', 'ベトナム'),
    ('LY VAN PHUC', 'リー ヴァン フック', 'フック', 'ベトナム'),
    ('DINH THI THAO', 'ディン ティ タオ', 'タオ', 'ベトナム'),
    ('TRINH VAN NAM', 'チン ヴァン ナム', 'ナム', 'ベトナム'),
    ('MAI THI PHUONG', 'マイ ティ フオン', 'プー', 'ベトナム'),
    ('DAO QUOC KHANH', 'ダオ クオック カイン', 'カイン', 'ベトナム'),
    ('CAO VAN TAI', 'カオ ヴァン タイ', 'タイ', 'ベトナム'),
    ('HA THI YEN', 'ハー ティ イエン', 'イエン', 'ベトナム'),
    ('LUONG VAN TIEN', 'ルオン ヴァン ティエン', 'ティエン', 'ベトナム'),
    ('PHAN MINH TRI', 'ファン ミン チー', 'チー', 'ベトナム'),
    ('VO THI KIM', 'ヴォー ティ キム', 'キム', 'ベトナム'),
    ('CHAU VAN HUNG', 'チャウ ヴァン フン', 'フン', 'ベトナム'),
    ('TA THI BICH', 'ター ティ ビック', 'ビック', 'ベトナム'),
    ('TRUONG VAN LONG', 'チュオン ヴァン ロン', 'ロン', 'ベトナム'),
    ('LAM THI MY', 'ラム ティ ミー', 'ミー', 'ベトナム'),
    ('NGUYEN QUOC BAO', 'グエン クオック バオ', 'バオ', 'ベトナム'),
    ('TRAN VAN DAT', 'トラン ヴァン ダット', 'ダット', 'ベトナム'),
    ('LE THI DIEM', 'レ ティ ディエム', 'ディエム', 'ベトナム'),
    ('PHAM VAN GIANG', 'ファム ヴァン ザン', 'ザン', 'ベトナム'),
    ('HOANG THI HANH', 'ホアン ティ ハイン', 'ハイン', 'ベトナム'),
    ('VU VAN HOANG', 'ヴー ヴァン ホアン', 'ホアン', 'ベトナム'),
    ('DO THI HONG', 'ドー ティ ホン', 'ホン', 'ベトナム'),
    ('BUI VAN HUY', 'ブイ ヴァン フイ', 'フイ', 'ベトナム'),
    ('DANG QUOC KHANH', 'ダン クオック カイン', 'カン', 'ベトナム'),
    ('NGO THI LIEN', 'ンゴ ティ リエン', 'リエン', 'ベトナム'),
    ('DUONG VAN MANH', 'ズオン ヴァン マン', 'マン', 'ベトナム'),
    ('DINH VAN NGHIA', 'ディン ヴァン ギア', 'ギア', 'ベトナム'),
    ('TRINH THI NHU', 'チン ティ ニュー', 'ニュー', 'ベトナム'),
    ('MAI VAN QUAN', 'マイ ヴァン クアン', 'クアン', 'ベトナム'),
    ('DAO THI QUYNH', 'ダオ ティ クイン', 'クイン', 'ベトナム'),
    ('CAO QUOC SANG', 'カオ クオック サン', 'サン', 'ベトナム'),
    ('HA VAN TAI', 'ハー ヴァン タイ', 'タイボーイ', 'ベトナム'),
    ('LUONG THI TAM', 'ルオン ティ タム', 'タム', 'ベトナム'),
    ('PHAN VAN THANG', 'ファン ヴァン タン', 'タン', 'ベトナム'),
    ('VO VAN THINH', 'ヴォー ヴァン ティン', 'ティン', 'ベトナム'),
    ('CHAU THI TRANG', 'チャウ ティ チャン', 'チャン', 'ベトナム'),
    ('TA VAN TRUNG', 'ター ヴァン チュン', 'チュン', 'ベトナム'),
    ('TRUONG THI TUYET', 'チュオン ティ トゥエット', 'トゥエ', 'ベトナム'),
    ('LAM VAN VINH', 'ラム ヴァン ヴィン', 'ヴィン', 'ベトナム'),

    # ネパール
    ('ADHIKARI SANTOSH', 'アディカリ サントス', 'サントス', 'ネパール'),
    ('SHRESTHA PRABIN', 'ｼｭﾚｽﾀ ﾌﾟﾗﾋﾞﾝ', 'プラビン', 'ネパール'),
    ('THAPA ANIL', 'タパ アニル', 'アニル', 'ネパール'),
    ('GURUNG BIKAS', 'ｸﾞﾙﾝ ﾋﾞｶｽ', 'ビカス', 'ネパール'),
    ('MAHARJAN PRADIP', 'マハルジャン プラディップ', 'プラディップ', 'ネパール'),
    ('TAMANG SUMAN', 'ﾀﾏﾝ ｽﾏﾝ', 'スマン', 'ネパール'),
    ('POUDEL RAMESH', 'ポウデル ラメシュ', 'ラメシュ', 'ネパール'),
    ('KHADKA DIPAK', 'カドカ ディパク', 'ディパク', 'ネパール'),
    ('SHARMA BISHAL', 'シャルマ ビシャル', 'ビシャル', 'ネパール'),
    ('BHANDARI KABITA', 'バンダリ カビタ', 'カビタ', 'ネパール'),
    ('NEUPANE LAXMAN', 'ネウパネ ラクスマン', 'ラクスマン', 'ネパール'),
    ('BHATTARAI ROSHAN', 'バッタライ ロシャン', 'ロシャン', 'ネパール'),
    ('BASNET PRAKASH', 'バスネット プラカシュ', 'プラカシュ', 'ネパール'),
    ('MAGAR GANESH', 'マガルフ ガネシュ', 'ガネシュ', 'ネパール'),
    ('GHIMIRE MANOJ', 'ギミレ マノジ', 'マノジ', 'ネパール'),
    ('DAHAL SURENDRA', 'ダハル スレンドラ', 'スレン', 'ネパール'),
    ('SUBEDI RAJESH', 'スベディ ラジェシュ', 'ラジェ', 'ネパール'),
    ('RAI KIRAN', 'ライ キラン', 'キラン', 'ネパール'),
    ('PANDIT SANJIB', 'パンディット サンジブ', 'サンジブ', 'ネパール'),
    ('KHANAL NABIN', 'カナル ナビン', 'ナビン', 'ネパール'),
    ('LAMA TSHERING', 'ラマ ツェリン', 'ツェリン', 'ネパール'),
    ('RAWAT BIMAL', 'ラワット ビマル', 'ビマル', 'ネパール'),
    ('TIWARI ARJUN', 'ティワリ アルジュン', 'アルジュン', 'ネパール'),
    ('REGMI SAROJ', 'レグミ サロジ', 'サロジ', 'ネパール'),
    ('CHHETRI SUNIL', 'チェトリ スニル', 'スニル', 'ネパール'),
    ('BISTA BIJAY', 'ビスタ ビジャイ', 'ビジャイ', 'ネパール'),
    ('ADHIKARI POOJA', 'アディカリ プジャ', 'プジャ', 'ネパール'),
    ('SHRESTHA SABINA', 'シュレスタ サビナ', 'サビナ', 'ネパール'),
    ('THAPA MANISHA', 'タパ マニシャ', 'マニシャ', 'ネパール'),
    ('GURUNG ALINA', 'グルン アリナ', 'アリナ', 'ネパール'),
    ('TAMANG SANGITA', 'タマン サンギタ', 'サンギタ', 'ネパール'),
    ('POUDEL SUSMITA', 'ポウデル ススミタ', 'ススミタ', 'ネパール'),
    ('KHADKA RITU', 'カドカ リトゥ', 'リトゥ', 'ネパール'),
    ('SHARMA ANITA', 'シャルマ アニタ', 'アニタ', 'ネパール'),
    ('BHANDARI DEEPA', 'バンダリ ディパ', 'ディパ', 'ネパール'),
    ('NEUPANE SITA', 'ネウパネ シタ', 'シタ', 'ネパール'),
    ('BHATTARAI GEETA', 'バッタライ ギタ', 'ギタ', 'ネパール'),
    ('BASNET PRATIMA', 'バスネット プラティマ', 'プラティ', 'ネパール'),
    ('MAGAR SUSMA', 'マガルフ ススマ', 'ススマ', 'ネパール'),
    ('GHIMIRE BANDANA', 'ギミレ バンダナ', 'バンダナ', 'ネパール'),
    ('DAHAL ARCHANA', 'ダハル アルチャナ', 'アルチャナ', 'ネパール'),
    ('SUBEDI MAMATA', 'スベディ ママタ', 'ママタ', 'ネパール'),
    ('RAI PREETI', 'ライ プリティ', 'プリティ', 'ネパール'),
    ('PANDIT KOPILA', 'パンディット コピラ', 'コピラ', 'ネパール'),
    ('KHANAL BINA', 'カナル ビナ', 'ビナ', 'ネパール'),
    ('LAMA MENUKA', 'ラマ メヌカ', 'メヌカ', 'ネパール'),
    ('RAWAT REKHA', 'ラワット レカ', 'レカ', 'ネパール'),
    ('TIWARI SMRITI', 'ティワリ スムリティ', 'スムリティ', 'ネパール'),
    ('REGMI MONIKA', 'レグミ モニカ', 'モニカ', 'ネパール'),
    ('CHHETRI SUNITA', 'チェトリ スニタ', 'スニタ', 'ネパール'),
    ('BISTA KALPAN', 'ビスタ カルパナ', 'カルパナ', 'ネパール'),

    # 中国
    ('李 偉', 'リ ウェイ', 'Li Wei', '中国'),
    ('張 麗', 'ﾁｬﾝ ﾘｰ', 'Zhang Li', '中国'),
    ('王 秀英', 'オウ シュウエイ', 'Wang Xiuying', '中国'),
    ('陳 勇', 'ﾁﾝ ﾕｳ', 'Chen Yong', '中国'),
    ('劉 洋', 'リュウ ヨウ', 'Liu Yang', '中国'),
    ('楊 剛', 'ﾔﾝ ｺﾞｳ', 'Yang Gang', '中国'),
    ('黄 小玲', 'コウ ショウレイ', 'Huang Xiaoling', '中国'),
    ('周 傑', 'ｼｭｳ ｹﾂ', 'Zhou Jie', '中国'),
    ('呉 磊', 'ウー レイ', 'Wu Lei', '中国'),
    ('徐 敏', 'ジョ ビン', 'Xu Min', '中国'),
    ('孫 涛', 'スン タオ', 'Sun Tao', '中国'),
    ('朱 芳', 'ジュ ファン', 'Zhu Fang', '中国'),
    ('馬 超', 'マ チョウ', 'Ma Chao', '中国'),
    ('胡 楠', 'フー ナン', 'Hu Nan', '中国'),
    ('郭 靖', 'グオ ジン', 'Guo Jing', '中国'),
    ('何 平', 'ホー ピン', 'He Ping', '中国'),
    ('高 峰', 'ガオ フォン', 'Gao Feng', '中国'),
    ('林 爽', 'リン シュアン', 'Lin Shuang', '中国'),
    ('鄭 浩', 'ジェン ハオ', 'Zheng Hao', '中国'),
    ('謝 娜', 'シエ ナー', 'Xie Na', '中国'),
    ('韓 寒', 'ハン ハン', 'Han Han', '中国'),
    ('唐 嫣', 'タン イエン', 'Tang Yan', '中国'),
    ('馮 紹峰', 'フォン シャオフォン', 'Feng Shaofeng', '中国'),
    ('于 朦朧', 'ユー モンロン', 'Yu Menglong', '中国'),
    ('董 潔', 'ドン ジエ', 'Dong Jie', '中国'),
    ('蕭 敬騰', 'シャオ ジンタン', 'Xiao Jingteng', '中国'),
    ('程 瀟', 'チョン シャオ', 'Cheng Xiao', '中国'),
    ('曹 操', 'ツァオ ツァオ', 'Cao Cao', '中国'),
    ('袁 詠儀', 'ユエン ヨンイー', 'Yuan Yongyi', '中国'),
    ('鄧 超', 'ダン チャオ', 'Deng Chao', '中国'),
    ('許 凱', 'シュー カイ', 'Xu Kai', '中国'),
    ('傅 菁', 'フー ジン', 'Fu Jing', '中国'),
    ('沈 騰', 'シェン タン', 'Shen Teng', '中国'),
    ('曾 舜晞', 'ゾン シュンシー', 'Zeng Shunxi', '中国'),
    ('彭 于晏', 'ポン ユィーイエン', 'Peng Yuyan', '中国'),
    ('呂 布', 'ルー ブー', 'Lu Bu', '中国'),
    ('蘇 軾', 'スー シー', 'Su Shi', '中国'),
    ('盧 瀚霆', 'ルー ハンティン', 'Lu Hanting', '中国'),
    ('蒋 欣', 'ジャン シン', 'Jiang Xin', '中国'),
    ('賈 乃亮', 'ジア ナイリャン', 'Jia Nailiang', '中国'),

    # ミャンマー
    ('AUNG KYAW ZIYA', 'アウン チョー ズィーヤ', 'ズィーヤ', 'ミャンマー'),
    ('THIDA KYAW SAN', 'ﾃｨﾀﾞ ﾁｮｰ ｻﾝ', 'サン', 'ミャンマー'),
    ('SAW WIN NAING', 'ソー ウィン ナイン', 'ソー', 'ミャンマー'),
    ('NAN MOE MOE KHAING', 'ﾅﾝ ﾓｰ ﾓｰ ｶｲﾝ', 'カイン', 'ミャンマー'),
    ('HLAING ZIN ZAW', 'ライン ズィン ゾー', 'ゾー', 'ミャンマー'),
    ('MYO MIN THANT', 'ミョー ミン タント', 'タント', 'ミャンマー'),
    ('ZAW ZAW AUNG', 'ゾー ゾー アウン', 'アウン', 'ミャンマー'),
    ('SU SU HLAING', 'スー スー ライン', 'スー', 'ミャンマー'),
    ('KO KO NAING', 'コー コー ナイン', 'ココ', 'ミャンマー'),
    ('PHYU PHYU THIN', 'ピュー ピュー ティン', 'ピュー', 'ミャンマー'),
    ('TIN MAUNG LAT', 'ティン マウン ラッ', 'ラッ', 'ミャンマー'),
    ('MAY THU AUNG', 'メイ トゥー アウン', 'メイ', 'ミャンマー'),
    ('KYAW MIN HTET', 'チョー ミン テッ', 'テッ', 'ミャンマー'),
    ('EI EI KHAING', 'エイ エイ カイン', 'エイ', 'ミャンマー'),
    ('TUN TUN WIN', 'トゥン トゥン ウィン', 'トゥン', 'ミャンマー'),
    ('NILAR WIN', 'ニラー ウィン', 'ニラー', 'ミャンマー'),
    ('MOE KYAW THURA', 'モー チョー トゥラ', 'トゥラ', 'ミャンマー'),
    ('KHAING ZIN THAW', 'カイン ズィン トー', 'トー', 'ミャンマー'),
    ('WAI YAN PHYO', 'ワイ ヤン ピョー', 'ピョー', 'ミャンマー'),
    ('THET HTET SAN', 'テッ テッ サン', 'テッテッ', 'ミャンマー'),
    ('MIN THURA ZAW', 'ミン トゥラ ゾー', 'ミン', 'ミャンマー'),
    ('HAY MAR LWIN', 'ヘイ マー ルイン', 'ヘイマー', 'ミャンマー'),
    ('AUNG PHYO WAI', 'アウン ピョー ワイ', 'アウンワイ', 'ミャンマー'),
    ('SHWE YEE WIN', 'シュエ イー ウィン', 'シュエ', 'ミャンマー'),

    # スリランカ
    ('DISANAYAKA ACHIRA', 'ディサナヤカ アチラ', 'アチラ', 'スリランカ'),
    ('JAYAWARDANA SAPUMAL', 'ｼﾞｬﾔﾜﾙﾀﾞﾅ ｻﾌﾟﾏﾙ', 'サプマル', 'スリランカ'),
    ('RATNAYAKA PRIYANTHA', 'ラトナヤカ プリヤンタ', 'プリ', 'スリランカ'),
    ('WICKRAMASINGHE GAYAN', 'ｳｨｸﾗﾏｼﾝﾊ ｶﾞﾔﾝ', 'ガヤン', 'スリランカ'),
    ('SENAVIRATHNA PRABATH', 'セナウィラトナ プラバート', 'プラバ', 'スリランカ'),
    ('PERERA DILSHAN', 'ペレラ ディルシャン', 'ディル', 'スリランカ'),
    ('SILVA KASUN', 'シルバ カスン', 'カス', 'スリランカ'),
    ('FERNANDO ROSHAN', 'フェルナンド ロシャン', 'ロシャ', 'スリランカ'),
    ('BANDARA CHAMARA', 'バンダラ チャマラ', 'チャマ', 'スリランカ'),
    ('KUMARA NUWAN', 'クマガラ ヌワン', 'ヌワ', 'スリランカ'),
    ('HERATH THILINA', 'ヘラト ティリナ', 'ティリ', 'スリランカ'),
    ('RANASINGHE LAHIRU', 'ラナシンハ ラヒル', 'ラヒ', 'スリランカ'),
    ('DISSANAYAKE MALINDA', 'ディッサナーヤカ マリンダ', 'マリ', 'スリランカ'),
    ('GUNASEKARA ISURU', 'グナセカラ イスル', 'イス', 'スリランカ'),
    ('WIJESINGHE CHAMIKA', 'ウィジェシンハ チャミカ', 'チャミ', 'スリランカ'),
    ('WEERASINGHE SANJAYA', 'ウィーラシンハ サンジャヤ', 'サンジャ', 'スリランカ'),

    # 台湾
    ('林 冠宇', 'リン グァンユウ', 'Lin Guanyu', '台湾'),
    ('黄 雅婷', 'ﾎﾜﾝ ﾔｰﾃｨﾝ', 'Huang Yating', '台湾'),
    ('郭 宗翰', 'クオ ゾンハン', 'Guo Zonghan', '台湾'),
    ('張 宇軒', 'ﾁｬﾝ ﾕｰｼｭｱﾝ', 'Chang Yuxuan', '台湾'),
    ('陳 詩涵', 'チン スーハン', 'Chen Shihan', '台湾'),
    ('王 伯融', 'ワン ボーロン', 'Wang Porung', '台湾'),
    ('李 冠霖', 'リー グアンリン', 'Li Guanlin', '台湾'),
    ('呉 佩慈', 'ウー ペイツー', 'Wu Peici', '台湾'),

    # 韓国
    ('金 敏錫', 'キム ミンソク', 'Min-seok', '韓国'),
    ('李 道賢', 'ﾘ ﾄﾞﾋｮﾝ', 'Do-hyun', '韓国'),
    ('朴 智恩', 'パク ジウン', 'Ji-eun', '韓国'),
    ('崔 俊昊', 'ﾁｪ ｼﾞｭﾝﾎ', 'Jun-ho', '韓国'),
    ('鄭 宇盛', 'チョン ウソン', 'Woo-sung', '韓国'),
    ('姜 棟元', 'カン ドンウォン', 'Dong-won', '韓国'),
    ('趙 寅成', 'チョ インソン', 'In-sung', '韓国'),
    ('韓 孝周', 'ハン ヒョジュ', 'Hyo-joo', '韓国'),
]

# 意図的に同姓同名にする3組（計3組×2名＝6名）
DUPLICATE_TARGETS = [
    # 1組目: ベトナム
    ('NGUYEN VAN TUAN', 'グエン ヴァン トゥアン', 'トゥアン', 'ベトナム'),
    # 2組目: ネパール
    ('THAPA ANIL', 'タパ アニル', 'アニル', 'ネパール'),
    # 3組目: 中国
    ('陳 勇', 'チン ユウ', 'Chen Yong', '中国'),
]

def generate_csv(file_path='students_200_test.csv', total=200):
    # ベースのユニーク名簿をシャッフル
    unique_pool = [n for n in UNIQUE_NAMES if n[0] not in [d[0] for d in DUPLICATE_TARGETS]]
    random.shuffle(unique_pool)

    # 200人分の枠を作成
    # 3組（6人分）は同姓同名、残り194人は完全ユニーク
    duplicate_count = len(DUPLICATE_TARGETS) * 2  # 6名
    unique_needed = total - duplicate_count      # 194名
    
    selected_students = []
    
    # 1. 重複組を追加
    for target in DUPLICATE_TARGETS:
        selected_students.append(target)
        selected_students.append(target)
        
    # 2. 残りを重複なしプールから追加
    selected_students.extend(unique_pool[:unique_needed])
    
    # ランダムに並び替え
    random.shuffle(selected_students)

    # 同姓同名が同じクラス・学科にならないよう割り当て
    # 割り当て履歴: name -> list of (dept, course, class)
    assigned_map = {}
    records = []

    for i, student_info in enumerate(selected_students, start=1):
        num_str = f"{i:04d}"
        if i % 7 == 0:
            student_id = f"２６Ａ{num_str}".translate(str.maketrans('0123456789', '０１２３４５６７８９'))
        else:
            student_id = f"26A{num_str}"

        name, furigana, nickname, nationality = student_info

        # 学科・コース・クラスの選択（同姓同名の場合は異なるクラスを強制選択）
        shuffled_classes = CLASSES_POOL.copy()
        random.shuffle(shuffled_classes)
        
        chosen_class = None
        for candidate in shuffled_classes:
            if name not in assigned_map or candidate not in assigned_map[name]:
                chosen_class = candidate
                break
        
        if not chosen_class:
            chosen_class = shuffled_classes[0]

        if name not in assigned_map:
            assigned_map[name] = []
        assigned_map[name].append(chosen_class)

        dept_name, course_name, class_name = chosen_class

        # 表記揺れの適用
        # 非漢字圏の氏名（英字）の全角・スペース揺れ
        formatted_name = name
        if nationality not in ['中国', '台湾', '韓国']:
            if i % 9 == 0:
                formatted_name = formatted_name.translate(str.maketrans(
                    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ',
                    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ '
                ))
            elif i % 5 == 0:
                formatted_name = formatted_name.replace(' ', ' ')

        # ニックネームの表記揺れ
        formatted_nick = nickname
        if nationality in ['中国', '台湾']:
            if i % 6 == 0:
                formatted_nick = formatted_nick.translate(str.maketrans(
                    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
                ))
        else:
            if i % 5 == 0:
                hankaku_map = str.maketrans(
                    'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー',
                    'ｱｲｳｴｵｶｷｸｹｺｻシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー'
                )
                formatted_nick = formatted_nick.translate(hankaku_map)

        if i % 4 == 0:
            class_name = class_name.translate(str.maketrans('12', '１２'))

        records.append([
            student_id,
            formatted_name,
            furigana,
            formatted_nick,
            nationality,
            dept_name,
            course_name,
            class_name
        ])

    with open(file_path, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['学籍番号', '氏名', 'フリガナ', 'ニックネーム', '国籍', '学科', 'コース', 'クラス'])
        writer.writerows(records)

    print(f"✅ CSV再出力完了: {file_path} （全 {total} 件）")
    print("【同姓同名として設定された3組】")
    for d in DUPLICATE_TARGETS:
        print(f" - {d[0]} ({d[3]}) -> それぞれ別学科・別クラスに配置")

if __name__ == '__main__':
    generate_csv()