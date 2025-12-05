from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """
    Стандартная пагинация для всех ViewSet'ов.

    Параметры:
        ?page=1          — номер страницы (по умолчанию 1)
        ?limit=20        — элементов на странице (по умолчанию 20, макс 100)

    Пример ответа:
    {
        "count": 150,
        "page": 1,
        "limit": 20,
        "total_pages": 8,
        "results": [...]
    }
    """
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'page': self.page.number,
            'limit': self.get_page_size(self.request),
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


# Алиасы для обратной совместимости
CustomPagination = StandardPagination
ContractPagination = StandardPagination
