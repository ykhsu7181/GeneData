"""filemanager URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.documentation import include_docs_urls
from files.views import GenomeFileViewSet  # 添加导入
from files import views

from django.http import JsonResponse

def debug_view(request):
    """Debug view to test if Django is receiving requests"""
    return JsonResponse({
        'status': 'Django is working',
        'path': request.path,
        'method': request.method,
        'headers': dict(request.headers)
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('gd/api/files/', include('files.urls')),
    path('gd/api/admin/', include('files.urls')),  # 添加管理后台API路由
    path('api/files/', include('files.urls')),
    path('api/admin/', include('files.urls')),  # 添加管理后台API路由（通过代理）
    path('api-auth/', include('rest_framework.urls')),
    path('docs/', include_docs_urls(title='文件管理API文档')),

    # Debug endpoint to test if Django is receiving requests
    path('gd/api/debug/', debug_view, name='debug'),

    # 添加兼容旧版路径的路由
    path('gd/api/download/', GenomeFileViewSet.as_view({'get': 'download_transcriptome'}), name='legacy-download'),
    # manual_download功能
    path('gd/api/manual_download/<str:filename>', views.download_manual_file, name='legacy-manual-download'),
]
