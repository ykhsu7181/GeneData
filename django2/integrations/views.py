from django.http import JsonResponse
from .services import fetch_rgi_ogigraph


def test_api(request):
    return JsonResponse({'message': 'integrations app is working'})


def rgi_ogigraph_view(request, ogi_id):
    try:
        data = fetch_rgi_ogigraph(ogi_id)

        result = {
            "ogi_id": ogi_id,
            "category_count": len(data.get("categories", [])),
            "node_count": len(data.get("nodes", [])),
            "link_count": len(data.get("links", [])),
            "sample_nodes": data.get("nodes", [])[:5],
        }

        return JsonResponse(result, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)