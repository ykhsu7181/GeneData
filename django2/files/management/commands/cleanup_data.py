import os
from django.core.management.base import BaseCommand
from django.conf import settings
from files.models import GenomeFile

class Command(BaseCommand):
    help = '清理错误的数据记录并修复转录组文件的分类'

    def handle(self, *args, **options):
        # 定义已知的组织类型，这些不应该被当作生物体
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
        
        # 1. 删除organism是组织类型的记录
        deleted_count = 0
        for tissue_type in tissue_types:
            count = GenomeFile.objects.filter(organism=tissue_type).count()
            if count > 0:
                self.stdout.write(f'删除organism为{tissue_type}的记录: {count}条')
                GenomeFile.objects.filter(organism=tissue_type).delete()
                deleted_count += count
        
        self.stdout.write(self.style.SUCCESS(f'共删除{deleted_count}条错误记录'))
        
        # 2. 检查转录组文件是否有正确的类别前缀
        fixed_count = 0
        for file_obj in GenomeFile.objects.filter(name__startswith='transcriptome.'):
            parts = file_obj.name.split('.')
            if len(parts) >= 3 and parts[1] in tissue_types:
                old_category = file_obj.category
                new_category = f"transcriptome.{parts[1]}"
                
                if old_category != new_category:
                    file_obj.category = new_category
                    file_obj.save()
                    fixed_count += 1
                    self.stdout.write(f'修复文件{file_obj.name}的类别: {old_category} -> {new_category}')
        
        self.stdout.write(self.style.SUCCESS(f'共修复{fixed_count}条转录组记录的类别'))
        
        self.stdout.write(self.style.SUCCESS('数据清理完成，请运行scan_files命令重新扫描文件')) 