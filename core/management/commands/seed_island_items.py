from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import IslandItem

SEED_ITEMS = [
    # 陸地（島）オブジェクト & 生物
    ('log', '丸太', -3.0, 1.0, 2.0, 0.0, True),
    ('ancient_tree', '大樹', 5.0, 1.2, -4.0, 0.5, True),
    ('palm_tree', 'ヤシの木', -5.0, 1.2, 3.0, 0.0, True),
    ('treasure_chest', '宝箱', 2.0, 1.0, 3.0, 0.0, True),
    ('bonfire', 'かがり火', -2.0, 1.0, -2.0, 0.0, True),
    ('camp_tent', 'キャンプテント', -4.0, 1.0, -3.0, 0.5, True),
    ('watchtower', '見張り塔', 4.0, 1.0, 4.0, 0.7, True),
    ('ancient_ruins', '古代遺跡', -4.5, 1.0, 1.5, 0.2, True),
    ('rabbit', 'ウサギ', 2.5, 1.0, 2.0, 0.0, True),
    ('deer', 'シカ', -1.0, 1.0, 2.5, 0.5, True),
    ('hound', '猟犬', 1.0, 1.0, 1.5, 0.0, True),
    ('squirrel', 'リス', 3.0, 1.0, -1.0, 0.0, False),
    ('berry_bush', 'ベリーの茂み', 1.5, 1.0, 4.0, 0.0, False),

    # 海上・海中オブジェクト & 生物 (Lv.20〜)
    ('merchant_ship', '行商人船', 12.0, 0.0, 8.0, 0.5, True),
    ('drifting_raft', '漂流いかだ', -11.0, 0.0, 7.0, 0.2, True),
    ('navigation_buoy', '航路ブイ', 9.0, 0.0, -10.0, 0.0, True),
    ('lighthouse', '灯台', -13.0, 0.0, -12.0, 0.0, True),
    ('ghost_ship', '幽霊船', 14.0, 0.0, -13.0, 0.8, True),
    ('dolphin', 'イルカ', 10.0, 0.0, -11.0, 0.0, True),
    ('sea_turtle', 'ウミガメ', -10.0, 0.0, -8.0, 0.0, True),
    ('humpback_whale', 'ザトウクジラ', 15.0, 0.0, 12.0, 0.0, False),
    ('coral_reef', 'サンゴ礁', 8.0, 0.0, 10.0, 0.0, False),

    # 空中オブジェクト & 生物 (Lv.50〜)
    ('refueling_balloon', '給油気球', -6.0, 12.0, 6.0, 0.0, True),
    ('floating_island', '浮遊島', 0.0, 12.0, -14.0, 0.0, True),
    ('seagull', 'カモメ', 2.0, 12.0, 2.0, 0.0, True),
    ('wyvern', 'ワイバーン', -8.0, 14.0, -6.0, 0.0, False),
]

def seed_items_for_user(user, force=False, wipe=False):
    """ユーザーに対して一通りの配置用シードアイテムを作成する"""
    if wipe:
        IslandItem.objects.filter(user=user).delete()

    if force or wipe or IslandItem.objects.filter(user=user).count() == 0:
        created_count = 0
        for item_type, name, px, py, pz, ry, is_placed in SEED_ITEMS:
            if not IslandItem.objects.filter(user=user, item_type=item_type, name=name).exists():
                IslandItem.objects.create(
                    user=user,
                    item_type=item_type,
                    name=name,
                    price=IslandItem.get_default_price(item_type),
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
        parser.add_argument('--wipe', action='store_true', help='既存アイテムをすべて削除してから再生成します')

    def handle(self, *args, **options):
        username = options.get('username')
        force = options.get('force', False)
        wipe = options.get('wipe', False)

        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.filter(is_active=True)

        total_created = 0
        for user in users:
            cnt = seed_items_for_user(user, force=force, wipe=wipe)
            total_created += cnt
            self.stdout.write(self.style.SUCCESS(f"User {user.username}: {cnt} items created."))

        self.stdout.write(self.style.SUCCESS(f"Done! Total {total_created} seed items registered across {users.count()} users."))
