import Link from "next/link";
import Image from "next/image";
import React, { useState, useEffect } from "react";

import DrawerIcon from "../../public/icons/drawer.svg";
import SettingsIcon from "../../public/icons/settings.svg";
import BotIcon from "../../public/icons/bot.svg";
import DropdownIcon from "../../public/icons/dropdown.svg";
import TwitterIcon from "../../public/icons/twitter.svg";
import GithubIcon from "../../public/icons/github.svg";
import LinkedinIcon from "../../public/icons/linkedin.svg";

export default function Sidebar() {
  const [bots, setBots] = useState([]);

  useEffect(() => {
    const fetchBots = async () => {
      const response = await fetch("/api/get_bots");
      const data = await response.json();
      setBots(data);
    };

    fetchBots();
  }, []);

  const toggleDropdown = () => {
    const dropdown = document.getElementById("dropdown-toggle");
    dropdown.classList.toggle("hidden");
  };

  return (
    <>
      {/* Mobile Toggle */}
      <button
        data-drawer-target="logo-sidebar"
        data-drawer-toggle="logo-sidebar"
        aria-controls="logo-sidebar"
        type="button"
        className="inline-flex items-center p-2 mt-2 ml-3 text-sm text-gray-500 rounded-lg sm:hidden hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-200"
      >
        <DrawerIcon className="w-6 h-6" />
      </button>

      {/* Sidebar */}
      <div
        id="logo-sidebar"
        className="fixed top-0 left-0 z-40 w-64 h-screen transition-transform -translate-x-full sm:translate-x-0"
      >
        <div className="flex flex-col h-full px-3 py-4 overflow-y-auto bg-gray-100">
          <div className="pb-10">
            <Link href="/" className="flex items-center justify-evenly  mb-5">
              <Image
                src="/images/embedchain.png"
                alt="Embedchain Logo"
                width={45}
                height={0}
                className="block h-auto w-auto"
              />
              <span className="self-center text-2xl font-bold whitespace-nowrap">
                Embedchain
              </span>
            </Link>
            <ul className="space-y-2 font-medium text-lg">
              {/* Settings */}
              <li>
                <Link
                  href="/"
                  className="flex items-center p-2 text-gray-900 rounded-lg hover:bg-gray-200 group"
                >
                  <SettingsIcon className="w-6 h-6 text-gray-600 transition duration-75 group-hover:text-gray-900" />
                  <span className="ml-3">Settings</span>
                </Link>
              </li>

              {/* Bots */}
              {bots.length !== 0 && (
                <li>
                  <button
                    type="button"
                    className="flex items-center w-full p-2 text-base text-gray-900 transition duration-75 rounded-lg group hover:bg-gray-200"
                    onClick={toggleDropdown}
                  >
                    <BotIcon className="w-6 h-6 text-gray-600 transition duration-75 group-hover:text-gray-900" />
                    <span className="flex-1 ml-3 text-left whitespace-nowrap">
                      Bots
                    </span>
                    <DropdownIcon className="w-3 h-3" />
                  </button>
                  <ul
                    id="dropdown-toggle"
                    className="hidden text-sm py-2 space-y-2"
                  >
                    {bots.map((bot, index) => (
                      <React.Fragment key={index}>
                        <li>
                          <Link
                            href={`/${bot.slug}/app`}
                            className="flex items-center w-full p-2 text-gray-900 transition duration-75 rounded-lg pl-11 group hover:bg-gray-200"
                          >
                            {bot.name}
                          </Link>
                        </li>
                      </React.Fragment>
                    ))}
                  </ul>
                </li>
              )}
            </ul>
          </div>
          <div className="bg-gray-200 absolute bottom-0 left-0 right-0 h-20"></div>

          {/* Social Icons */}
          <div className="mt-auto mb-3 flex flex-row justify-evenly sticky bottom-3">
            <a href="https://twitter.com/embedchain" target="blank">
              <TwitterIcon className="w-6 h-6 text-gray-600 transition duration-75 hover:text-gray-900" />
            </a>
            <a href="https://github.com/embedchain/embedchain" target="blank">
              <GithubIcon className="w-6 h-6 text-gray-600 transition duration-75 hover:text-gray-900" />
            </a>
            <a
              href="https://www.linkedin.com/company/embedchain"
              target="blank"
            >
              <LinkedinIcon className="w-6 h-6 text-gray-600 transition duration-75 hover:text-gray-900" />
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
