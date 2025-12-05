"""
Генератор PDF для инвентаризационной ведомости кабинета.
"""
from io import BytesIO
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from django.conf import settings


def register_fonts():
    """Регистрация шрифтов с поддержкой кириллицы"""
    # Пробуем найти DejaVu шрифт (обычно есть в системе)
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/Library/Fonts/Arial Unicode.ttf',
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                return 'CustomFont'
            except:
                continue

    # Fallback — используем Helvetica (без кириллицы, но работает)
    return 'Helvetica'


def generate_room_inventory_pdf(room):
    """
    Генерация PDF инвентаризационной ведомости для кабинета.

    Формат как на фото:
    - Заголовок с названием
    - Таблица: №, Инвентарный номер, Ески номери, Название, Ед.изм, Кол-во
    - Подпись ответственного
    """
    buffer = BytesIO()

    # Создаём документ
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    # Регистрируем шрифт
    font_name = register_fonts()

    # Стили
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=14,
        alignment=1,  # Center
        spaceAfter=5 * mm
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=12,
        alignment=1,
        spaceAfter=10 * mm
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10
    )

    elements = []

    # Заголовок
    university_name = room.building.university.name if room.building.university else "Университет"
    building_name = room.building.name
    room_number = room.number
    room_name = room.name or ""

    title_text = f"Esap-sanaq kabineti tiykargi qurallardin"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph("DIZIMI", subtitle_style))

    # Информация о кабинете
    info_text = f"{university_name} / {building_name} / Kabinet {room_number} {room_name}"
    elements.append(Paragraph(info_text, normal_style))
    elements.append(Spacer(1, 5 * mm))

    # Получаем оборудование в кабинете
    equipment_list = room.equipment.filter(is_active=True).select_related('type').order_by('name')

    # Заголовки таблицы
    table_data = [
        ['K/c\nNo', 'Inventar nomeri', 'Eski nomeri', 'Tiykargi qurallardin ati', 'Olshem\nbirligi', 'Sani']
    ]

    # Данные таблицы
    for idx, eq in enumerate(equipment_list, 1):
        table_data.append([
            str(idx),
            eq.inn or '-',
            '-',  # Eski номер (старый номер) - можно добавить поле в модель
            eq.name,
            'dana',  # Единица измерения
            '1'  # Количество (каждое оборудование = 1 шт)
        ])

    # Если нет оборудования
    if len(table_data) == 1:
        table_data.append(['', '', '', 'Оборудование отсутствует', '', ''])

    # Создаём таблицу
    col_widths = [12 * mm, 40 * mm, 35 * mm, 60 * mm, 18 * mm, 15 * mm]
    table = Table(table_data, colWidths=col_widths)

    # Стиль таблицы
    table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Данные
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # № по центру
        ('ALIGN', (4, 1), (5, -1), 'CENTER'),  # Ед.изм и Кол-во по центру
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),

        # Границы
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15 * mm))

    # Подпись
    date_str = timezone.now().strftime('%d.%m.%Y')
    signature_text = f"Materialliq jawaapker: __________________ /{' ' * 20}/"
    elements.append(Paragraph(signature_text, normal_style))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(f"Sana: {date_str}", normal_style))

    # Собираем PDF
    doc.build(elements)

    buffer.seek(0)
    return buffer


def generate_room_inventory_pdf_simple(room):
    """
    Упрощённая версия PDF без сложных шрифтов.
    Использует базовые ASCII символы.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    styles = getSampleStyleSheet()
    elements = []

    # Заголовок
    elements.append(Paragraph("INVENTORY LIST", styles['Heading1']))
    elements.append(Spacer(1, 5 * mm))

    # Информация
    university_name = room.building.university.name if room.building.university else "University"
    info = f"Building: {room.building.name} | Room: {room.number}"
    elements.append(Paragraph(info, styles['Normal']))
    elements.append(Spacer(1, 10 * mm))

    # Получаем оборудование
    equipment_list = room.equipment.filter(is_active=True).select_related('type').order_by('name')

    # Таблица
    table_data = [['#', 'INN', 'Name', 'Type', 'Status', 'Qty']]

    for idx, eq in enumerate(equipment_list, 1):
        table_data.append([
            str(idx),
            eq.inn or '-',
            eq.name[:30] + '...' if len(eq.name) > 30 else eq.name,
            eq.type.name if eq.type else '-',
            eq.status,
            '1'
        ])

    if len(table_data) == 1:
        table_data.append(['', '', 'No equipment', '', '', ''])

    col_widths = [10 * mm, 35 * mm, 50 * mm, 35 * mm, 25 * mm, 15 * mm]
    table = Table(table_data, colWidths=col_widths)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15 * mm))

    # Дата и подпись
    date_str = timezone.now().strftime('%d.%m.%Y')
    elements.append(Paragraph(f"Date: {date_str}", styles['Normal']))
    elements.append(Paragraph("Responsible: ____________________", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer
