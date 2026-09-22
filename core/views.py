from django.shortcuts import render


def home(request):
    """Home page - project overview and navigation."""
    context = {
        'project_name': 'Granit Sales Analytics ERP',
        'apps': [
            {
                'name': 'SMS Campaign Analysis',
                'description': 'Upload Excel, analyze customer purchase lift',
                'status': 'Stage 3 - Pending',
            },
            {
                'name': 'Sales Explorer',
                'description': 'Filter and explore sales by product, client, store, period',
                'status': 'Stage 4 - Pending',
            },
            {
                'name': 'Promotion Effectiveness',
                'description': 'Compare promo results vs baseline and YoY',
                'status': 'Stage 5 - Pending',
            },
        ],
    }
    return render(request, 'core/home.html', context)
