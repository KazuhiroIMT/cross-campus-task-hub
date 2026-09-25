from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import IslandItem

SEED_ITEMS = [
    # ① 自然・ガーデニング系
    ('palm_tree', '南国のヤシの木', -5.0, 2.7, 3.0, 0.0, True),
    ('broadleaf_tree', '新緑の広葉樹', 5.0, 2.7, -4.0, 0.5, True),
    ('cherry_tree', '満開の桜の木', -4.0, 2.7, -5.0, 0.2, True),
    ('flower_bed', '彩り華やかな花壇', 2.0, 2.7, 4.0, 0.0, True),
    ('sunflower_cluster', '大輪のヒマワリ畑', 4.0, 2.7, 2.0, 0.3, True),
    ('garden_light', '優しく灯るガーデンライト', -2.0, 2.7, 3.5, 0.0, True),
    ('bonfire', '幻想的なかがり火', -3.0, 2.7, -2.0, 0.0, True),
    ('fountain', 'きらめく中央噴水', 0.0, 2.7, 0.0, 0.0, True),
    ('small_pond', '透明な小さな池', 3.5, 2.7, -1.5, 0.0, True),

    # ② リゾート・休憩設備
    ('wooden_bench', 'くつろぎの木製ベンチ', -1.5, 2.7, 1.8, 0.4, True),
    ('hammock', '風がそよぐハンモック', -5.5, 2.7, -1.0, 1.2, True),
    ('beach_parasol_set', 'ビーチパラソル＆サマーベッド', 6.0, 2.7, 1.0, -0.8, True),
    ('wood_deck', '広々ウッドデッキ', 0.0, 2.7, -4.5, 0.0, True),
    ('cafe_table_set', '青空カフェテーブルセット', 1.5, 2.7, -4.0, 0.0, True),
    ('watchtower', '冒険の見張り台', 4.5, 2.7, 4.5, 0.7, True),
    ('cottage', '安らぎのコテージ小屋', -4.5, 2.7, -3.5, 0.5, True),

    # ③ 生き物（動物・マスコット）
    ('shiba_inu', '元気なシバイヌ', 1.0, 2.7, 2.0, 0.0, True),
    ('calico_cat', 'のんびり三毛猫', -1.0, 2.7, 2.5, 0.5, True),
    ('white_rabbit', '愛くるしい白ウサギ', 2.5, 2.7, 3.0, 0.0, True),
    ('capybara', 'おっとりカピバラ', 3.0, 2.7, -0.5, 0.2, True),
    ('penguin', 'よちよちペンギン', -6.5, 2.7, 3.5, 0.0, True),
    ('seagull', '優雅なカモメ', 0.0, 4.0, 1.0, 0.0, True),
    ('parakeet', 'カラフルなインコ', 4.8, 2.7, -3.8, 0.0, True),

    # ④ 海洋エリアアイテム (Lv.20〜)
    ('yacht', '豪華なリゾートヨット', 12.0, 0.0, 8.0, 0.5, True),
    ('overwater_cottage', '南国の水上コテージ', -12.0, 0.0, -10.0, 0.0, True),
    ('dolphin_spot', '跳ねるイルカスポット', 10.0, 0.0, -12.0, 0.0, True),

    # ⑤ 上空エリアアイテム (Lv.50〜)
    ('hot_air_balloon', '優雅なふわふわ気球', -6.0, 15.0, 6.0, 0.0, True),
    ('rainbow_arch', '輝く虹のアーチ', 0.0, 10.0, -15.0, 0.0, True),
]

def seed_items_for_user(user, force=False):
    """ユーザーに対して一通りの配置用シードアイテムを作成する"""
    if force or IslandItem.objects.filter(user=user).count() == 0:
        created_count = 0
        for item_type, name, px, py, pz, ry, is_placed in SEED_ITEMS:
            # 重複作成を防ぐ（非forceの場合）
            if not IslandItem.objects.filter(user=user, item_type=item_type, name=name).exists():
                IslandItem.objects.create(
                    user=user,
                    item_type=item_type,
                    name=name,
                    position_x=px,
                    position_y=py,
                    position_z=pz,
                    rotation_y=ry,
                    is_placed=is_placed
                )
                created_count += 1
        return created_count
    return 0


class Command(BaseCommand):
    help = '島アイテム・動物の初期データ（シード）を一括生成します。'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='対象ユーザー名（指定がなければ全アクティブユーザー）')
        parser.add_argument('--force', action='store_true', help='既存アイテムがあっても強制的に不足アイテムを追加作成します')

    def handle(self, *args, **options):
        username = options.get('username')
        force = options.get('force', False)

        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.filter(is_active=True)

        total_created = 0
        for user in users:
            cnt = seed_items_for_user(user, force=force)
            total_created += cnt
            self.stdout.write(self.style.SUCCESS(f"User {user.username}: {cnt} items created."))

        self.stdout.write(self.style.SUCCESS(f"Done! Total {total_created} seed items registered across {users.count()} users."))
