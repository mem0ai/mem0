import { useState } from "react";

export default function SetOpenAIKey({ setIsKeyPresent }) {
  const [openAIKey, setOpenAIKey] = useState("");
  const [status, setStatus] = useState("");

  const handleOpenAIKey = async (e) => {
    e.preventDefault();
    const response = await fetch("/api/set_key", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ openAIKey }),
    });

    if (response.ok) {
      setOpenAIKey("");
      setStatus("success");
      setIsKeyPresent(true);
    } else {
      setStatus("fail");
    }

    setTimeout(() => {
      setStatus("");
    }, 3000);
  };

  return (
    <>
      <div className="w-full">
        {/* Set Open AI Key */}
        <h2 className="text-xl font-bold text-gray-800">SET OPENAI KEY</h2>
        <form className="py-2" onSubmit={handleOpenAIKey}>
          <label
            htmlFor="openai_key"
            className="block mb-2 text-sm font-medium text-gray-900"
          >
            OpenAI Key
          </label>
          <div className="flex flex-col sm:flex-row gap-x-4 gap-y-4">
            <input
              type="password"
              id="openai_key"
              className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
              placeholder="Enter Open AI Key here"
              required
              value={openAIKey}
              onChange={(e) => setOpenAIKey(e.target.value)}
            />
            <button
              type="submit"
              className="h-fit text-white bg-black hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center"
            >
              Submit
            </button>
          </div>
          {status === "success" && (
            <div className="text-green-600 text-sm font-bold py-1">
              Your Open AI key has been saved successfully!
            </div>
          )}
          {status === "fail" && (
            <div className="text-red-600 text-sm font-bold py-1">
              An error occurred while saving your OpenAI Key!
            </div>
          )}
        </form>
      </div>
    </>
  );
}
