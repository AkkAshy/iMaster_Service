from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Room
from io import BytesIO
import qrcode
from django.core.files import File

@receiver(post_save, sender=Room)
def generate_qr_code(sender, instance, created, **kwargs):
    """
    Генерация QR-кода для кабинета после создания
    """
    if (created or not instance.qr_code) and instance.number and instance.floor:
        try:
            # Данные для QR-кода
            qr_data = f"Room: {instance.number}"
            if instance.name:
                qr_data += f", {instance.name}"
            if instance.floor:
                qr_data += f", Floor: {instance.floor.number}"

            # Генерация QR-кода
            qr = qrcode.make(qr_data)

            img_io = BytesIO()
            qr.save(img_io, format='PNG')
            img_io.seek(0)

            filename = f"qr_{instance.number}.png"
            
            # Сохраняем файл без повторного вызова save()
            instance.qr_code.save(filename, File(img_io), save=False)
            instance.save(update_fields=['qr_code'])

        except Exception as e:
            # Логируем ошибки, если что-то пошло не так
            print(f"[QR Code Error] Не удалось сгенерировать QR-код для комнаты {instance.id}: {e}")