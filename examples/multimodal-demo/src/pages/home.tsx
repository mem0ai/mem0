import { useState } from "react";
import ApiSettingsPopup from "../components/api-settings-popup";
import Memories from "../components/memories";
import Header from "../components/header";
import Messages from "../components/messages";
import InputArea from "../components/input-area";
import ChevronToggle from "../components/chevron-toggle";


export default function Home() {
  const [isMemoriesExpanded, setIsMemoriesExpanded] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <>
      <ApiSettingsPopup isOpen={isSettingsOpen} setIsOpen={setIsSettingsOpen} />
      <div className="flex h-screen bg-background">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <Header setIsSettingsOpen={setIsSettingsOpen} />

          {/* Messages */}
          <Messages />

          {/* Input Area */}
          <InputArea />
        </div>

        {/* Chevron Toggle */}
        <ChevronToggle
          isMemoriesExpanded={isMemoriesExpanded}
          setIsMemoriesExpanded={setIsMemoriesExpanded}
        />

        {/* Memories Sidebar */}
        <Memories isMemoriesExpanded={isMemoriesExpanded} />
      </div>
    </>
  );
}
