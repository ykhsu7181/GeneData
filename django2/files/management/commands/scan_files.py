import os
from django.core.management.base import BaseCommand
from django.conf import settings
from files.models import FileType, GenomeFile, Organism, FileCategory
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '扫描文件目录并将文件添加到数据库，同时清理不存在的文件记录'

    def handle(self, *args, **options):
        directory = settings.MANUAL_FILES_DIR
        files_added = 0
        files_removed = 0
        
        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'目录不存在: {directory}'))
            return
        
        self.stdout.write(f'扫描目录: {directory}')
        
        # 获取所有现存文件的路径集合
        existing_files = set()
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                existing_files.add(file_path)
        
        self.stdout.write(f'找到{len(existing_files)}个文件')
        
        # 清理数据库中不存在的文件记录
        for file_obj in GenomeFile.objects.all():
            if file_obj.file_path not in existing_files:
                self.stdout.write(f'删除记录: {file_obj.name} (文件不存在)')
                file_obj.delete()
                files_removed += 1
        
        # 获取有效的文件扩展名映射
        extension_map = {}
        for file_type in FileType.objects.all():
            extension_map[file_type.extension] = file_type
            
        # 定义有效的组织类型，这些不应被视为生物体/物种
        tissue_types = ['all', 'root', 'stem', 'leaf', 'panicles', 'shoot']
        
        # 列出文件类别选项
        self.stdout.write(f'有效的文件类别:')
        for cat_choice, cat_name in GenomeFile.FILE_CATEGORY_CHOICES:
            self.stdout.write(f'  - {cat_choice}: {cat_name}')
            
        # 扫描目录中的文件（包括子目录）
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                self.stdout.write(f'处理文件: {filename}')
                
                # 检查文件是否已存在
                if GenomeFile.objects.filter(file_path=file_path).exists():
                    self.stdout.write(f'  文件已存在于数据库中，跳过: {filename}')
                    continue
                    
                parts = filename.split('.')
                extension = parts[-1] if len(parts) > 1 else ''
                
                # 特殊处理压缩文件格式
                if extension in ['gz', 'zip', 'bz2', 'xz']:
                    if len(parts) > 2:
                        extension = f"{parts[-2]}.{parts[-1]}"  # 例如: fasta.gz
                
                # 获取或创建文件类型
                file_type = extension_map.get(extension)
                if not file_type:
                    file_type = FileType.objects.create(
                        name=extension.upper() if extension else 'UNKNOWN',
                        extension=extension
                    )
                    extension_map[extension] = file_type
                    self.stdout.write(f'  创建新文件类型: {extension}')
                
                # 处理不同的文件命名格式
                
                # 1. 处理格式: transcriptome.type.organism.extension[.gz]
                # 例如: transcriptome.leaf.MH63.fastaq.gz
                if len(parts) >= 4 and parts[0] == 'transcriptome' and parts[1] in tissue_types:
                    tissue_type = parts[1]
                    organism = parts[2]
                    category = f"transcriptome.{tissue_type}"
                    
                    self.stdout.write(f'  处理转录组类型文件: {filename}, tissue_type={tissue_type}, organism={organism}')
                    
                    # 确保这个organism是有效的生物体，而不是组织类型
                    if organism in tissue_types:
                        # 如果organism是组织类型，可能文件命名有问题，跳过或处理
                        self.stdout.write(self.style.WARNING(f"  文件名格式有问题，organism与组织类型冲突: {filename}"))
                        continue
                    
                    # 确保organism存在于Organism表中
                    try:
                        org_obj, created = Organism.objects.get_or_create(
                            code=organism,
                            defaults={'name': organism}
                        )
                        if created:
                            self.stdout.write(f'  创建新生物体记录: {organism}')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  创建Organism记录失败: {str(e)}"))
                    
                    # 检查文件是否已存在（基于organism和category的组合）
                    existing = GenomeFile.objects.filter(
                        organism=organism,
                        category=category
                    ).first()
                    
                    if existing:
                        # 如果已存在记录但文件路径不同，更新文件路径
                        if existing.file_path != file_path:
                            existing.file_path = file_path
                            existing.name = filename
                            existing.size = os.path.getsize(file_path)
                            existing.save()
                            self.stdout.write(f'  更新文件路径: {filename}')
                        else:
                            self.stdout.write(f'  文件记录已存在: {filename}')
                        continue
                    
                    # 创建新记录
                    try:
                        GenomeFile.objects.create(
                            name=filename,
                            organism=organism,
                            category=category,
                            file_path=file_path,
                            file_type=file_type,
                            size=os.path.getsize(file_path)
                        )
                        files_added += 1
                        self.stdout.write(f'  添加文件: {filename} (organism={organism}, category={category})')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  创建文件记录失败: {str(e)}"))
                    
                # 2. 处理格式: category.organism.extension[.gz]
                # 例如: transcriptome.MH63.fasta, genome.ZS97.fasta.gz
                elif len(parts) >= 3:
                    category = parts[0]
                    organism = parts[1]
                    
                    self.stdout.write(f'  处理标准格式文件: {filename}, category={category}, organism={organism}')
                    
                    # 确保organism不是组织类型
                    if organism in tissue_types:
                        # 这可能是转录组类型的文件，使用不同的解析方式
                        if category == 'transcriptome':
                            tissue_type = organism  # 组织类型实际上是第二个部分
                            organism = parts[2] if len(parts) > 2 else 'unknown'  # 生物体是第三个部分
                            category = f"transcriptome.{tissue_type}"
                            self.stdout.write(f'  重新解析为转录组类型文件: tissue_type={tissue_type}, organism={organism}')
                        else:
                            # 如果不是转录组但organism是组织类型，可能文件命名有问题
                            self.stdout.write(self.style.WARNING(f"  文件名格式有问题，organism与组织类型冲突: {filename}"))
                            continue
                    
                    # 验证category
                    valid_category = False
                    for cat_choice, _ in GenomeFile.FILE_CATEGORY_CHOICES:
                        if cat_choice == category:
                            valid_category = True
                            break
                    
                    self.stdout.write(f"  类别'{category}'有效: {valid_category}")
                    
                    # 使用动态方法验证organism，不再使用硬编码的ORGANISM_CHOICES
                    # 我们认为organism有效，如果它不是组织类型
                    valid_organism = organism not in tissue_types
                    self.stdout.write(f"  生物体'{organism}'有效: {valid_organism}")
                            
                    if valid_category and valid_organism:
                        # 确保organism存在于Organism表中
                        try:
                            org_obj, created = Organism.objects.get_or_create(
                                code=organism,
                                defaults={'name': organism}
                            )
                            if created:
                                self.stdout.write(f'  创建新生物体记录: {organism}')
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"  创建Organism记录失败: {str(e)}"))
                        
                        # 检查文件是否已存在（基于organism和category的组合）
                        existing = GenomeFile.objects.filter(
                            organism=organism,
                            category=category
                        ).first()
                        
                        if existing:
                            # 如果已存在记录但文件路径不同，更新文件路径
                            if existing.file_path != file_path:
                                existing.file_path = file_path
                                existing.name = filename
                                existing.size = os.path.getsize(file_path)
                                existing.save()
                                self.stdout.write(f'  更新文件路径: {filename}')
                            else:
                                self.stdout.write(f'  文件记录已存在: {filename}')
                            continue
                        
                        # 创建新记录
                        try:
                            GenomeFile.objects.create(
                                name=filename,
                                organism=organism,
                                category=category,
                                file_path=file_path,
                                file_type=file_type,
                                size=os.path.getsize(file_path)
                            )
                            files_added += 1
                            self.stdout.write(f'  添加文件: {filename} (organism={organism}, category={category})')
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  创建文件记录失败: {str(e)}"))
                    else:
                        # 如果不符合预期格式，记录但不抛出错误
                        self.stdout.write(self.style.WARNING(f"  文件名格式不符合预期: {filename} (category有效:{valid_category}, organism有效:{valid_organism})"))
                
                else:
                    # 如果不符合预期格式，记录但不抛出错误
                    self.stdout.write(self.style.WARNING(f"  文件名格式不符合预期: {filename} (parts数量不足)"))
        
        self.stdout.write(self.style.SUCCESS(f'成功添加 {files_added} 个文件，删除 {files_removed} 个不存在的文件记录')) 