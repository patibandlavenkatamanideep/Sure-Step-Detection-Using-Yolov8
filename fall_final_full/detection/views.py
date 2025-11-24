from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
import os
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
import cv2
from django.core.files.storage import FileSystemStorage
from ultralytics import YOLO
from django.conf import settings
from django.http import StreamingHttpResponse, JsonResponse
import time
from django.core.mail import EmailMessage
import glob
import shutil

# Create your views here.
@login_required(login_url='login')
def index(request):
    return render(request,'index.html')

@login_required(login_url='login')
def faq(request):
    return render(request,'faq.html')

@login_required(login_url='login')
@csrf_exempt
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        subject = request.POST.get("subject")
        message = request.POST.get("message")

        if not name or not email or not subject or not message:
            return JsonResponse({"success": False, "error": "All fields are required."})

        # Send Email (Replace with your SMTP settings)
        try:
            send_mail(
                subject=f"New Contact Message: {subject}",
                message=f"Name: {name}\nEmail: {email}\n\n{message}",
                from_email="pavanreddy901405@gmail.com",  # Replace with your email
                recipient_list=["pavanreddy901405@gmail.com"],  # Replace with the admin email
                fail_silently=False,
            )
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return render(request, "contact.html")

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, "Invalid username or password")

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('index')

def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        # Check if username is at least 6 characters long
        if len(username) < 6:
            messages.error(request, "Username must be at least 6 characters long")
            return redirect('signup')

        # Check if email is valid
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            messages.error(request, "Invalid email address")
            return redirect('signup')

        # Check if passwords match
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect('signup')

        # Check if password is at least 8 characters long
        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long")
            return redirect('signup')

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return redirect('signup')

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already taken")
            return redirect('signup')

        # Create new user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()

        messages.success(request, "Account created successfully! You can now log in.")
        return redirect('index')

    return render(request, 'signup.html')


# Load YOLO model
model = YOLO(os.path.join(settings.BASE_DIR, "best.pt"))

def detect_fall(image_path):
    results = model(image_path)  # Run YOLOv8 on the image
    detected_filename = os.path.basename(image_path)
    detected_image_path = os.path.join(settings.MEDIA_ROOT, "results", detected_filename)

    fall_detected = False

    for result in results:
        result.save(filename=detected_image_path)
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = model.names[cls_id]
            if "fall" in class_name.lower():
                fall_detected = True

    if fall_detected:
        try:
            email = EmailMessage(
                subject="Image-related Fall Alert: SureStep Detection",
                body=f"A fall has been detected in the uploaded image: {detected_filename}",
                from_email="pavanreddy901405@gmail.com",
                to=["pavanreddy901405@gmail.com"],
            )
            email.attach_file(detected_image_path)
            email.send(fail_silently=False)
        except Exception as e:
            print(f"Failed to send image alert email: {e}")

    return f'/media/results/{detected_filename}'

def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
        filename = fs.save(image.name, image)
        uploaded_image_url = f'/media/uploads/{filename}'
        image_path = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)

        # Process image with YOLO
        detected_image_url = detect_fall(image_path)

        return JsonResponse({
            'uploaded_image_url': uploaded_image_url,
            'detected_image_url': detected_image_url,
            'status': 'success'
        })  # Return JSON response

    # If it's a GET request, render the upload page
    return render(request, 'upload.html')

def process_video(request):
    video_path = request.GET.get('video_path', None)  # Get video path from query

    if not video_path or not os.path.exists(video_path):
        return JsonResponse({"error": "Invalid video path"}, status=400)

    detected_filename = os.path.splitext(os.path.basename(video_path))[0] + ".mp4"
    detected_video_path = os.path.join(settings.MEDIA_ROOT, "results", detected_filename)

    os.makedirs(os.path.join(settings.MEDIA_ROOT, "results"), exist_ok=True)

    def generate():
        """Yields progress updates for the frontend"""

        # Simulated progress up to 90%
        for progress in range(0, 90, 10):
            time.sleep(1)  # Simulate processing time
            yield f"data: {progress}\n\n"

        # Run YOLOv8 on video
        results = model(
            video_path,
            save=True,
            project=os.path.join(settings.MEDIA_ROOT, "results"),
            name="output"
        )

        # Collect all detected classes
        detected_classes = []
        for frame_result in results:
            for box in frame_result.boxes:
                cls_id = int(box.cls[0])
                class_name = frame_result.names[cls_id]
                detected_classes.append(class_name)

        # Locate YOLO-detected video (often saved as .avi)
        output_folder = os.path.join(settings.MEDIA_ROOT, "results", "output")
        avi_file = None
        for file in os.listdir(output_folder):
            if file.endswith(".avi"):
                avi_file = os.path.join(output_folder, file)
                break

        if avi_file:
            # Convert .avi to .mp4
            cap = cv2.VideoCapture(avi_file)
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            out = cv2.VideoWriter(detected_video_path, fourcc, fps, (width, height))

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)

            cap.release()
            out.release()

            # Remove the old avi file and its folder
            os.remove(avi_file)
            os.rmdir(output_folder)

        # Check if "fallen" or "falling" was detected
        if "Fallen" in detected_classes or "Falling" in detected_classes:
            subject = "Falling/Fallen Event Detected"
            body = (
                "A falling or fallen event was detected in the video.\n\n"
                "Please see the attached video for more details."
            )
            email = EmailMessage(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,  # Ensure DEFAULT_FROM_EMAIL is set in Django settings
                ["pavanreddy901405@gmail.com"],
            )
            # Attach the MP4 file
            if os.path.exists(detected_video_path):
                email.attach_file(detected_video_path)
            email.send(fail_silently=False)

        # Finally, yield the 100% progress with the filename
        yield f"data:100|{detected_filename}\n\n"

    return StreamingHttpResponse(generate(), content_type="text/event-stream")


def upload_video(request):
    if request.method == 'POST' and request.FILES.get('video'):
        video = request.FILES['video']
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
        filename = fs.save(video.name, video)
        uploaded_video_url = f'/media/uploads/{filename}'
        video_path = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)

        return JsonResponse({
            'uploaded_video_url': uploaded_video_url,
            'video_path': video_path  # Send correct video path
        })

    return render(request, 'upload_video.html')