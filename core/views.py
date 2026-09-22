from django.shortcuts import render
from django.utils.translation import gettext as _


def home(request):
    """Home page - project overview and navigation."""
    context = {
        'project_name': _('Granit Sales Analytics ERP'),
        'apps': [
            {
                'name': _('SMS Campaign Analysis'),
                'description': _('Upload Excel, analyze customer purchase lift'),
                'status': _('Stage 3 — Ready'),
                'url': 'campaign_list',
            },
            {
                'name': _('Sales Explorer'),
                'description': _('Filter and explore sales by product, client, store, period'),
                'status': _('Stage 4 — Pending'),
            },
            {
                'name': _('Promotion Effectiveness'),
                'description': _('Compare promo results vs baseline and YoY'),
                'status': _('Stage 5 — Pending'),
            },
        ],
    }
    return render(request, 'core/home.html', context)
