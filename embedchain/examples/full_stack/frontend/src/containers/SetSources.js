import { useState } from "react";
import PlusIcon from "../../public/icons/plus.svg";
import CrossIcon from "../../public/icons/cross.svg";
import YoutubeIcon from "../../public/icons/youtube.svg";
import PDFIcon from "../../public/icons/pdf.svg";
import WebIcon from "../../public/icons/web.svg";
import DocIcon from "../../public/icons/doc.svg";
import SitemapIcon from "../../public/icons/sitemap.svg";
import TextIcon from "../../public/icons/text.svg";

export default function SetSources({
  setChats,
  embedding_model,
  setSelectChat,
}) {
  const [sourceName, setSourceName] = useState("");
  const [sourceValue, setSourceValue] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const dataTypes = {
    youtube_video: "YouTube Video",
    pdf_file: "PDF File",
    web_page: "Web Page",
    doc_file: "Doc File",
    sitemap: "Sitemap",
    text: "Text",
  };

  const dataIcons = {
    youtube_video: <YoutubeIcon className="w-5 h-5 mr-3" />,
    pdf_file: <PDFIcon className="w-5 h-5 mr-3" />,
    web_page: <WebIcon className="w-5 h-5 mr-3" />,
    doc_file: <DocIcon className="w-5 h-5 mr-3" />,
    sitemap: <SitemapIcon className="w-5 h-5 mr-3" />,
    text: <TextIcon className="w-5 h-5 mr-3" />,
  };

  const handleDropdownClose = () => {
    setIsDropdownOpen(false);
    setSourceName("");
    setSelectChat(true);
  };
  const handleDropdownSelect = (dataType) => {
    setSourceName(dataType);
    setSourceValue("");
    setIsDropdownOpen(false);
    setSelectChat(false);
  };

  const handleAddDataSource = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    const addDataSourceEntry = {
      sender: "B",
      message: `Adding the following ${dataTypes[sourceName]}: ${sourceValue}`,
    };
    setChats((prevChats) => [...prevChats, addDataSourceEntry]);
    let name = sourceName;
    let value = sourceValue;
    setSourceValue("");
    const response = await fetch("/api/add_sources", {
      method: "POST",
      body: JSON.stringify({
        embedding_model,
        name,
        value,
      }),
      headers: {
        "Content-Type": "application/json",
      },
    });
    if (response.ok) {
      const successEntry = {
        sender: "B",
        message: `Successfully added ${dataTypes[sourceName]}!`,
      };
      setChats((prevChats) => [...prevChats, successEntry]);
    } else {
      const errorEntry = {
        sender: "B",
        message: `Failed to add ${dataTypes[sourceName]}. Please try again.`,
      };
      setChats((prevChats) => [...prevChats, errorEntry]);
    }
    setSourceName("");
    setIsLoading(false);
    setSelectChat(true);
  };

  return (
    <>
      <div className="w-fit">
        <button
          type="button"
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="w-fit p-2.5 rounded-xl text-white bg-black hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300"
        >
          <PlusIcon className="w-6 h-6" />
        </button>
        {isDropdownOpen && (
          <div className="absolute left-0 bottom-full bg-white border border-gray-300 rounded-lg shadow-lg mb-2">
            <ul className="py-1">
              <li
                className="block px-4 py-2 text-sm text-black cursor-pointer hover:bg-gray-200"
                onClick={handleDropdownClose}
              >
                <span className="flex items-center text-red-600">
                  <CrossIcon className="w-5 h-5 mr-3" />
                  Close
                </span>
              </li>
              {Object.entries(dataTypes).map(([key, value]) => (
                <li
                  key={key}
                  className="block px-4 py-2 text-sm text-black cursor-pointer hover:bg-gray-200"
                  onClick={() => handleDropdownSelect(key)}
                >
                  <span className="flex items-center">
                    {dataIcons[key]}
                    {value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {sourceName && (
        <form
          onSubmit={handleAddDataSource}
          className="w-full flex flex-col sm:flex-row gap-y-2 gap-x-2 items-center"
        >
          <div className="w-full">
            <input
              type="text"
              placeholder="Enter URL, Data or File path here..."
              className="text-sm w-full border-2 border-black rounded-xl focus:outline-none focus:border-blue-800 sm:pl-4 h-11"
              required
              value={sourceValue}
              onChange={(e) => setSourceValue(e.target.value)}
            />
          </div>
          <div className="w-full sm:w-fit">
            <button
              type="submit"
              disabled={isLoading}
              className={`${
                isLoading ? "opacity-60" : ""
              } w-full bg-black hover:bg-blue-800 rounded-xl text-lg text-white px-6 h-11`}
            >
              Send
            </button>
          </div>
        </form>
      )}
    </>
  );
}
