"use client";
import { GlobalState } from "./contexts/GlobalContext";
import Component from "./pages/home";


export default function Home() {
  return (
    <div>
      <GlobalState>
        <Component />
      </GlobalState>
    </div>
  );
}
