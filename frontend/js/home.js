// 首页交互：导航滚动态、入场动画、视频兜底。
(function () {
  // 1. 导航在滚动后变为实底
  var nav = document.getElementById("siteNav");
  function onScroll() {
    if (nav) nav.classList.toggle("scrolled", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // 2. 视频自动播放兜底（部分浏览器需用户交互后才能有声播放，静音自动播放通常允许）
  var video = document.querySelector(".hero-video");
  if (video) {
    var tryPlay = function () {
      var p = video.play();
      if (p && p.catch) p.catch(function () { /* 静音自动播放被阻止时保持 poster 展示 */ });
    };
    tryPlay();
    document.addEventListener("click", tryPlay, { once: true });
  }

  // 3. 入场动画
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("visible"); });
  }
})();
