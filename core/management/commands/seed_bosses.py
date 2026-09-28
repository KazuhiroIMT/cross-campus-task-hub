import os
import zlib
import struct
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.conf import settings
from core.services import BOSS_TEMPLATES, ensure_active_department_boss, ensure_initial_department_achievements


def create_placeholder_png(width=200, height=200, color=(220, 50, 50)):
    """Generate a valid PNG image in pure Python"""
    png_sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    ihdr_chunk = struct.pack('>I', len(ihdr_data)) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)

    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter type 0
        for x in range(width):
            raw_data.extend(color)

    compressed = zlib.compress(bytes(raw_data))
    idat_crc = zlib.crc32(b'IDAT' + compressed)
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)

    iend_crc = zlib.crc32(b'IEND')
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)

    return png_sig + ihdr_chunk + idat_chunk + iend_chunk


class Command(BaseCommand):
    help = "20段階ドラゴンボスマスタの初期化・シードコマンド"

    def handle(self, *args, **options):
        # 1. 物理的な画像アセットディレクトリおよび画像の生成確認
        base_dir = settings.BASE_DIR
        boss_img_dir = os.path.join(base_dir, 'core', 'static', 'core', 'images', 'bosses')
        os.makedirs(boss_img_dir, exist_ok=True)

        created_count = 0
        for template in BOSS_TEMPLATES:
            file_name = os.path.basename(template['image_path'])
            file_path = os.path.join(boss_img_dir, file_name)
            if not os.path.exists(file_path):
                lvl = template['boss_level']
                r = min(255, 100 + lvl * 7)
                g = max(0, 180 - lvl * 8)
                b = max(0, 50 + (lvl % 5) * 30)
                png_bytes = create_placeholder_png(width=200, height=200, color=(r, g, b))
                with open(file_path, 'wb') as f:
                    f.write(png_bytes)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created boss image asset: {file_name}"))

        # 2. 初期部署実績のロード
        ensure_initial_department_achievements()

        # 3. 全部署グループのアクティブボス確認・生成
        groups = Group.objects.all()
        if not groups.exists():
            default_group = Group.objects.create(name="教務課")
            groups = Group.objects.filter(pk=default_group.pk)
            self.stdout.write(self.style.SUCCESS("Created default department: 教務課"))

        for group in groups:
            battle = ensure_active_department_boss(group)
            self.stdout.write(self.style.SUCCESS(f"Department [{group.name}]: Active Boss = {battle.boss_name} (HP: {battle.current_hp}/{battle.max_hp})"))

        self.stdout.write(self.style.SUCCESS("20段階ドラゴンボスマスタのデータ初期化が完了しました。"))
