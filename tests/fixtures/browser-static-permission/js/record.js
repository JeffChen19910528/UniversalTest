// getUserMedia/MediaRecorder capability fixture: static analysis should
// detect this API usage, but no browser test may auto-grant microphone
// permission or auto-invoke this handler (spec section 23/45).
document.getElementById("record-button").addEventListener("click", function () {
  navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
    new MediaRecorder(stream);
  });
});
