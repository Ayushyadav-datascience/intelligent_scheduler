self.addEventListener("push", function(event) {
  const data = event.data.text();
  event.waitUntil(
    self.registration.showNotification("Task Notification", {
      body: data,
      icon: "https://www.gstatic.com/images/icons/material/system/2x/event_black_48dp.png",
    })
  );
});