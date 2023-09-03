import { useEffect, useState } from "react";
import { useRouter } from "next/router";

export default function DeleteBot() {
  const [bots, setBots] = useState([]);
  const router = useRouter();

  useEffect(() => {
    const fetchBots = async () => {
      const response = await fetch("/api/get_bots");
      const data = await response.json();
      setBots(data);
    };
    fetchBots();
  }, []);

  const handleDeleteBot = async (event) => {
    event.preventDefault();
    const selectedBotSlug = event.target.bot_name.value;
    if (selectedBotSlug === "none") {
      return;
    }
    const response = await fetch("/api/delete_bot", {
      method: "POST",
      body: JSON.stringify({ slug: selectedBotSlug }),
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      router.reload();
    }
  };

  return (
    <>
      {bots.length !== 0 && (
        <div className="w-full">
          {/* Delete Bot */}
          <h2 className="text-xl font-bold text-gray-800">DELETE BOTS</h2>
          <form className="py-2" onSubmit={handleDeleteBot}>
            <label className="block mb-2 text-sm font-medium text-gray-900">
              List of Bots
            </label>
            <div className="flex flex-col sm:flex-row gap-x-4 gap-y-4">
              <select
                name="bot_name"
                defaultValue="none"
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
              >
                <option value="none">Select a Bot</option>
                {bots.map((bot) => (
                  <option key={bot.slug} value={bot.slug}>
                    {bot.name}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="h-fit text-white bg-red-600 hover:bg-red-600/90 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center"
              >
                Delete
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
