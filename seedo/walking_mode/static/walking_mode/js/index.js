const MAX_CONCURRENT_REQUESTS = 2; // 동시에 처리될 수 있는 최대 요청 수
let activeRequests = 0; // 현재 처리 중인 요청 수
let soundQueue = []; // 재생할 오디오 파일을 저장하는 큐
let isPlaying = false; // 현재 오디오가 재생 중인지 여부

async function sendCameraImage(imageData) {
  try {
    const response = await fetch('{% url "walking_mode:test" %}', {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": "{{ csrf_token }}",
      },
      body: JSON.stringify({ image_data: imageData }),
    });

    const result = await response.json();
    console.log(result);
    // 탐지된 객체 정보를 HTML에 표시
    document.getElementById("object_detection").textContent = `Detection: ${result.od_classes.join(", ")} (Segmentation: ${result.seg_classes.join(", ")})`;

    // 이미지 표시
    const imgElement = document.getElementById("annotated-image");
    if (result.annotated_image) {
      imgElement.src = `data:image/jpeg;base64,${result.annotated_image}`;
      imgElement.style.display = "block";
    } else {
      imgElement.style.display = "none";
    }

    // TTS 오디오를 큐에 추가하고 재생 관리
    if (result.tts_audio_base64) {
      const audioData = `data:audio/mpeg;base64,${result.tts_audio_base64}`;
      soundQueue.push(audioData);
      playNextInQueue();
    }
  } catch (error) {
    console.error("Error sending camera image:", error);
  } finally {
    activeRequests--; // 요청이 완료되면 activeRequests를 감소
  }
}

function playNextInQueue() {
  if (isPlaying || soundQueue.length === 0) return;
  const audioData = soundQueue.shift();
  const sound = new Howl({
    src: [audioData],
    format: ["mp3"],
    autoplay: true,
    onend: function () {
      isPlaying = false;
      playNextInQueue();
    },
  });
  isPlaying = true;
  sound.play();
}

function captureImage(video, canvas) {
  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, 640, 480); // 해상도를 640x480으로 설정
  return canvas.toDataURL("image/jpeg", 1.0); // 이미지 포맷과 품질 설정
}

document.addEventListener("DOMContentLoaded", function () {
  let recording = false;
  const frameRate = 1; // frames per second
  let video = document.getElementById("video");
  let canvas = document.getElementById("canvas");
  async function maybeSendCameraImage() {
    if (recording && activeRequests < MAX_CONCURRENT_REQUESTS) {
      console.log(activeRequests);
      activeRequests++; // 새로운 요청을 시작하기 전에 activeRequests를 증가
      const imageData = captureImage(video, canvas);
      sendCameraImage(imageData);
    }
  }

  function startRecording() {
    recording = true;
    document.getElementById("recording-status").textContent = "Recording...";
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then(function (stream) {
        video.srcObject = stream;
        video.play();
      })
      .catch(function (error) {
        console.error("Error accessing camera:", error);
      });
    setInterval(maybeSendCameraImage, 1000 / frameRate);
  }

  function stopRecording() {
    recording = false;
    document.getElementById("recording-status").textContent = "Recording stopped.";
    video.pause();
    video.srcObject.getTracks().forEach((track) => track.stop());
  }

  document.getElementById("start-camera").addEventListener("click", startRecording);
  document.getElementById("stop-camera").addEventListener("click", stopRecording);
});
