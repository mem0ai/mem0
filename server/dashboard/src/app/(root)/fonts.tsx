import localFont from "next/font/local";

// Single InterVariable font that replaces both Inter and InterDisplay
export const Inter = localFont({
  src: [
    {
      path: "../../../public/fonts/InterVariable.woff2",
      weight: "100 900",
      style: "normal",
    },
    {
      path: "../../../public/fonts/InterVariable-Italic.woff2",
      weight: "100 900",
      style: "italic",
    },
  ],
  variable: "--font-inter",
  display: "swap",
});

// Alias for backward compatibility - points to the same InterVariable
export const InterDisplay = Inter;

export const Roboto = localFont({
  src: [
    {
      path: "../../../public/fonts/RobotoMono-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../../public/fonts/RobotoMono-Bold.ttf",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-roboto-mono",
  display: "swap",
});

// Fustat variable font (weights 200-800)
export const Fustat = localFont({
  src: [
    {
      path: "../../../public/fonts/Fustat-VariableFont_wght.ttf",
      weight: "200 800",
      style: "normal",
    },
  ],
  variable: "--font-fustat",
  display: "swap",
});

// DM Mono font (weights 300, 400, 500 with italic variants)
export const DMMono = localFont({
  src: [
    {
      path: "../../../public/fonts/DMMono-Light.ttf",
      weight: "300",
      style: "normal",
    },
    {
      path: "../../../public/fonts/DMMono-LightItalic.ttf",
      weight: "300",
      style: "italic",
    },
    {
      path: "../../../public/fonts/DMMono-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../../public/fonts/DMMono-Italic.ttf",
      weight: "400",
      style: "italic",
    },
    {
      path: "../../../public/fonts/DMMono-Medium.ttf",
      weight: "500",
      style: "normal",
    },
    {
      path: "../../../public/fonts/DMMono-MediumItalic.ttf",
      weight: "500",
      style: "italic",
    },
  ],
  variable: "--font-dm-mono",
  display: "swap",
});
