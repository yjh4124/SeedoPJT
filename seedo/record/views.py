import base64
import json
from pathlib import Path

import cv2
import environ
import numpy as np
import requests
from common.decorators import token_required
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from matching.models import UserRequest
from django.core.mail import send_mail
from django.conf import settings

from .models import Accident, Condition

# Create your views here.
User = get_user_model()

BASE_DIR = Path(__file__).resolve().parent.parent
# API 가져오기
env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)
env_path = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file=env_path)


@token_required
def broken_view(request, request_id):
    user = request.user
    # request_id가 보낸 요청과 받은 요청 중 파트너 허가된 목록반환
    user_requests = UserRequest.objects.filter((Q(requester=user) | Q(recipient=user)) & Q(is_accepted=True))

    partner_list = [{"user": user}]
    for user_request in user_requests:
        partner_info = {"user": (user_request.recipient if user_request.requester == user else user_request.requester)}
        partner_list.append(partner_info)

    # 조회하는 사용자의 파손 기록 조회
    broken_records = Condition.objects.filter(user=request_id).order_by("-condition_date", "-condition_time")
    broken_list = []
    for broken_record in broken_records:
        broken_info = {
            "broken_date": broken_record.condition_date,
            "broken_time": broken_record.condition_time,
            "broken_img": broken_record.condition_image,
            "broken_location": broken_record.condition_location,
        }
        broken_list.append(broken_info)

    selected_user = User.objects.get(id=request_id)

    context = {"selected_user": selected_user, "partner_list": partner_list, "broken_list": broken_list}
    return render(request, "record/break.html", context)


@token_required
def accident_view(request, request_id):
    user = request.user
    # request_id가 보낸 요청과 받은 요청 중 파트너 허가된 목록반환
    user_requests = UserRequest.objects.filter((Q(requester=user) | Q(recipient=user)) & Q(is_accepted=True))

    partner_list = [{"user": user}]
    for user_request in user_requests:
        partner_info = {"user": (user_request.recipient if user_request.requester == user else user_request.requester)}
        partner_list.append(partner_info)

    # 조회하는 사용자의 사고 기록 조회
    accident_records = Accident.objects.filter(user=request_id).order_by("-accident_date", "-accident_time")
    accident_list = []
    for accident_record in accident_records:
        accident_info = {
            "accident_date": accident_record.accident_date,
            "accident_time": accident_record.accident_time,
            "accident_video": accident_record.accident_video,
            "accident_location": accident_record.accident_location,
        }
        accident_list.append(accident_info)

    selected_user = User.objects.get(id=request_id)

    context = {"selected_user": selected_user, "partner_list": partner_list, "accident_list": accident_list}
    return render(request, "record/accident.html", context)


@token_required
def save_accident_view(request):
    if request.method == "POST":

        user_id = request.user.id
        latitude = request.POST["latitude"]
        longitude = request.POST["longitude"]
        video_file = request.FILES["video_file"]
        base_url = "https://apis.openapi.sk.com/tmap/geo/reversegeocoding?version=1&format=json&callback=result"
        params = {"lat": latitude, "lon": longitude, "coordType": "WGS84GEO", "addressType": "A10"}
        headers = {"appKey": env("TMAP_API_KEY")}
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            address = data["addressInfo"]["fullAddress"].split(",")[2]
        else:
            print("Failed to connect to TMAP API")
            address = None

        if address is None:
            address = "dummy_location"

        user = User.objects.get(id=user_id)

        accident = Accident.objects.create(user=user, accident_video=video_file, accident_location=address)
        user_requests = UserRequest.objects.filter((Q(requester=user) | Q(recipient=user)) & Q(is_accepted=True))

        for user_request in user_requests:
            recipient = user_request.requester if user_request.recipient == user else user_request.recipient
            subject = "사고 알림"
            message = f"{user.username} 님의 사고영상이 저장되었습니다."
            from_email = settings.EMAIL_HOST_USER
            recipient_list = [recipient.email]

            send_mail(subject, message, from_email, recipient_list)

        return JsonResponse({"status": "success", "accident_id": accident.id})

    return JsonResponse({"status": "error"}, status=400)


@token_required
def save_broken_view(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user_id = request.user.id
        broken_location = data.get("broken_address", "dummy_location")
        if broken_location is None:
            broken_location = "dummy_location"

        broken_img = data.get("broken_img", "")

        # Step 1: Decode the base64 encoded image to binary data
        img_data = base64.b64decode(broken_img)

        # Step 2: Convert the binary data to a NumPy array
        nparr = np.frombuffer(img_data, np.uint8)

        # Step 3: Decode the NumPy array to an OpenCV image
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Step 4: Encode the image to PNG format
        _, buffer = cv2.imencode(".png", img)

        # Step 5: Create a ContentFile from the image data
        image_file = ContentFile(buffer.tobytes(), name="broken_image.png")

        user = User.objects.get(id=user_id)

        broken = Condition.objects.create(user=user, condition_location=broken_location, condition_image=image_file)
        return JsonResponse({"status": "success", "broken_id": broken.id})

    return JsonResponse({"status": "error"}, status=400)
