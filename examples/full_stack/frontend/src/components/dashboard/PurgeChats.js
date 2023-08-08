import { useState } from "react";

export default function PurgeChats() {
  const [status, setStatus] = useState("");
  const handleChatsPurge = (event) => {
    event.preventDefault();
    localStorage.clear();
    setStatus("success");
    setTimeout(() => {
      setStatus(false);
    }, 3000);
  };

  return (
    <>
      <div className="w-full">
        {/* Purge Chats */}
        <h2 className="text-xl font-bold text-gray-800">PURGE CHATS</h2>
        <form className="py-2" onSubmit={handleChatsPurge}>
          <label className="block mb-2 text-sm font-medium text-red-600">
            Warning
          </label>
          <div className="flex flex-col sm:flex-row gap-x-4 gap-y-4">
            <div
              type="text"
              className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
            >
              The following action will clear all your chat logs. Proceed with
              caution!
            </div>
            <button
              type="submit"
              className="h-fit text-white bg-red-600 hover:bg-red-600/80 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center"
            >
              Purge
            </button>
          </div>
          {status === "success" && (
            <div className="text-green-600 text-sm font-bold py-1">
              Your chats have been purged!
            </div>
          )}
        </form>
      </div>
    </>
  );
}
