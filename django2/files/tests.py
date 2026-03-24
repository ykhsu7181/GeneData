# from django.test import TestCase
# from django.urls import reverse
# from rest_framework.test import APITestCase
# from rest_framework import status
# from .models import GenomeFile, FileType
# import os
# import tempfile
# from django.conf import settings

# class CoreBlocksAPITestCase(APITestCase):
#     """测试coreBlocks相关的API功能"""

#     def setUp(self):
#         """设置测试数据"""
#         # 创建文件类型
#         self.bed_file_type = FileType.objects.create(
#             name='BED',
#             extension='bed',
#             description='BED格式文件'
#         )

#         # 创建临时的coreBlocks文件
#         self.temp_dir = tempfile.mkdtemp()
#         self.coreblocks_content = """Chr01\t1166844\t1168953
# Chr01\t3374464\t3375382
# Chr02\t67166\t71265
# Chr02\t71266\t71840"""

#         self.coreblocks_file_path = os.path.join(self.temp_dir, 'coreBlocks.IR64.bed')
#         with open(self.coreblocks_file_path, 'w') as f:
#             f.write(self.coreblocks_content)

#         # 创建GenomeFile记录
#         self.genome_file = GenomeFile.objects.create(
#             name='coreBlocks.IR64.bed',
#             organism='IR64',
#             category='coreBlocks',
#             file_path=self.coreblocks_file_path,
#             file_type=self.bed_file_type,
#             size=len(self.coreblocks_content)
#         )

#     def tearDown(self):
#         """清理测试数据"""
#         import shutil
#         if os.path.exists(self.temp_dir):
#             shutil.rmtree(self.temp_dir)

#     def test_get_coreblocks_success(self):
#         """测试成功获取coreBlocks数据"""
#         # 临时修改settings中的MANUAL_FILES_DIR
#         original_dir = getattr(settings, 'MANUAL_FILES_DIR', None)
#         settings.MANUAL_FILES_DIR = self.temp_dir

#         try:
#             url = reverse('get-coreblocks')
#             response = self.client.get(url, {
#                 'organism': 'IR64',
#                 'chromosome': 'Chr01'
#             })

#             self.assertEqual(response.status_code, status.HTTP_200_OK)
#             data = response.json()
#             self.assertEqual(len(data), 2)  # Chr01有2个区块

#             # 验证第一个区块的数据
#             first_block = data[0]
#             self.assertEqual(first_block['seqid'], 'Chr01')
#             self.assertEqual(first_block['start'], 1166844)
#             self.assertEqual(first_block['end'], 1168953)
#             self.assertEqual(first_block['length'], 2109)

#         finally:
#             # 恢复原始设置
#             if original_dir:
#                 settings.MANUAL_FILES_DIR = original_dir

#     def test_get_coreblocks_missing_organism(self):
#         """测试缺少organism参数的情况"""
#         url = reverse('get-coreblocks')
#         response = self.client.get(url, {'chromosome': 'Chr01'})

#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('缺少必要的参数: organism', response.json()['error'])

#     def test_get_coreblocks_missing_chromosome(self):
#         """测试缺少chromosome参数的情况"""
#         url = reverse('get-coreblocks')
#         response = self.client.get(url, {'organism': 'IR64'})

#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('缺少必要的参数: chromosome', response.json()['error'])

#     def test_get_coreblocks_file_not_found(self):
#         """测试文件不存在的情况"""
#         url = reverse('get-coreblocks')
#         response = self.client.get(url, {
#             'organism': 'NonExistent',
#             'chromosome': 'Chr01'
#         })

#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#         self.assertIn('未找到 NonExistent 的coreBlocks文件', response.json()['error'])

# class GenomeFileModelTestCase(TestCase):
#     """测试GenomeFile模型"""

#     def test_coreblocks_category_in_choices(self):
#         """测试coreBlocks类别是否在选择项中"""
#         categories = [choice[0] for choice in GenomeFile.FILE_CATEGORY_CHOICES]
#         self.assertIn('coreBlocks', categories)

#     def test_create_coreblocks_file(self):
#         """测试创建coreBlocks文件记录"""
#         file_type = FileType.objects.create(
#             name='BED',
#             extension='bed'
#         )

#         genome_file = GenomeFile.objects.create(
#             name='coreBlocks.IR64.bed',
#             organism='IR64',
#             category='coreBlocks',
#             file_path='/path/to/coreBlocks.IR64.bed',
#             file_type=file_type,
#             size=1000
#         )

#         self.assertEqual(genome_file.category, 'coreBlocks')
#         self.assertEqual(genome_file.organism, 'IR64')
#         self.assertEqual(str(genome_file), 'IR64-coreBlocks-coreBlocks.IR64.bed')
