import re
from uuid import UUID
from rest_framework import serializers
from university.models import Room
from inventory.models import Equipment
from inventory.serializers import EquipmentSerializer
from university.serializers import RoomSerializer


class QRScanSerializer(serializers.Serializer):
    qr_data = serializers.CharField(required=True)

    def validate(self, data):
        qr_data = data['qr_data']
        user = self.context.get('request').user if self.context.get('request') else None

        # Старый формат: 'Room ID: 5\nNumber: 3'
        room_match = re.match(r'Room ID: (\d+)\nNumber: (.+)', qr_data)
        if room_match:
            room_id = int(room_match.group(1))
            room = Room.objects.filter(id=room_id).first()
            if room:
                return self._build_room_response(room, user)

        # Новый формат: UUID
        try:
            uuid_obj = UUID(qr_data)
            equipment = Equipment.objects.filter(uid=uuid_obj).first()
            if equipment and (not user or equipment.author == user):
                return self._build_equipment_response(equipment)

            room = Room.objects.filter(uid=uuid_obj).first()
            if room:
                return self._build_room_response(room, user)

        except ValueError:
            pass

        raise serializers.ValidationError("QR-код не соответствует ни одному оборудованию или кабинету")

    def _build_room_response(self, room, user):
        data = {
            'type': 'room',
            'data': RoomSerializer(room, context=self.context).data,
        }

        equipments = room.equipment.all()  # используем related_name='equipments'
        if user:
            equipments = equipments.filter(author=user)

        data['equipments'] = EquipmentSerializer(equipments, many=True, context=self.context).data
        return data

    def _build_equipment_response(self, equipment):
        return {
            'type': 'equipment',
            'data': EquipmentSerializer(equipment, context=self.context).data
        }