const HOST = window.location.origin;
const WALLET_URL =  red61.digital_wallet_url;
const WALLET_TITLE = "WALLET";
const WALLET_ID = "WALLET";
const EVENT_TYPES = {
	LOAD_DATA: 'LOAD_DATA'
};

const portalId = "portal-id";
const portal = document.getElementById(portalId);

if( portal ){
  portal.style.minHeight = "400px";
}


const postData = () => {
  const walletDataId = document.getElementById('data-for-digital-wallet');
  const iframe = document.getElementById(WALLET_ID);

  const jwt = walletDataId.getAttribute('data-jwt-token')
  const baseURL = walletDataId.getAttribute('data-rest-endpoint')
  const apiKey = walletDataId.getAttribute('data-public-key')
  const primaryColor = walletDataId.getAttribute('data-primary-color')
  const secondaryColor = walletDataId.getAttribute('data-secondary-color')
  const backToEventsLink = walletDataId.getAttribute('data-back-to-events-link')


  iframe.contentWindow.postMessage(
    JSON.stringify({
      url: window.location,
      localStorage: window.localStorage,
      sessionStorage: window.sessionStorage,
      cookies: document.cookie,
      userAgent: window.navigator.userAgent,
      eventType: EVENT_TYPES.LOAD_DATA,
      width: window.document.body.clientWidth,
      jwt,
      baseURL,
      apiKey,
      primaryColor,
			secondaryColor,
			backToEventsLink
    }),
    WALLET_URL
  );
};

const createIframe = () => {
  const iframe = document.createElement("iframe");

  iframe.setAttribute("src", WALLET_URL);
  iframe.setAttribute("title", WALLET_TITLE);
  iframe.setAttribute("id", WALLET_ID);
  iframe.setAttribute("frameBorder", 0);
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("loading", "lazy");
  iframe.setAttribute("allow", "microphone; camera; fullscreen");
  iframe.setAttribute("sandbox", "allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation");

  iframe.style.width = "100%";

  if ( portal ) {
    portal.appendChild(iframe);
  }

  return iframe;
};

const resizeIframe = (height) => {
  const iframe = document.getElementById(WALLET_ID);
  iframe.style.height = height + "px";
}

const navigateTo = (path) => {
  window.location.href = window.location.origin + path;
}

window.addEventListener("load", (event) => {
  const iframe = createIframe();
  iframe.onload = () => postData();
});

window.addEventListener("message", (event) => {
  switch(event.data.type) {
    case 'HEIGHT':
        return resizeIframe(event.data.height)
    case 'NAVIGATION':
      return navigateTo(event.data.path)
    default:  () => {}
  }
});
