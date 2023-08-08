import { useState } from "react";
import { useRouter } from "next/router";

export default function CreateBot() {
  const [botName, setBotName] = useState("");
  const [status, setStatus] = useState("");
  const router = useRouter();

  const handleCreateBot = async (e) => {
    e.preventDefault();
    const data = {
      name: botName,
    };

    const response = await fetch("/api/create_bot", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (response.ok) {
      const botSlug = botName.toLowerCase().replace(/\s+/g, "_");
      router.push(`/${botSlug}/app`);
    } else {
      setBotName("");
      setStatus("fail");
      setTimeout(() => {
        setStatus("");
      }, 3000);
    }
  };

  return (
    <>
      <div className="w-full">
        {/* Create Bot */}
        <h2 className="text-xl font-bold text-gray-800">CREATE BOT</h2>
        <form className="py-2" onSubmit={handleCreateBot}>
          <label
            htmlFor="bot_name"
            className="block mb-2 text-sm font-medium text-gray-900"
          >
            Name of Bot
          </label>
          <div className="flex flex-col sm:flex-row gap-x-4 gap-y-4">
            <input
              type="text"
              id="bot_name"
              className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
              placeholder="Eg. Naval Ravikant"
              required
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
            />
            <button
              type="submit"
              className="h-fit text-white bg-black hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center"
            >
              Submit
            </button>
          </div>
          {status === "fail" && (
            <div className="text-red-600 text-sm font-bold py-1">
              An error occurred while creating your bot!
            </div>
          )}
        </form>
      </div>
    </>
  );
}
