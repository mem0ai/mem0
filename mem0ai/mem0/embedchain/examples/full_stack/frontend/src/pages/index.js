import Wrapper from "@/components/PageWrapper";
import Sidebar from "@/containers/Sidebar";
import CreateBot from "@/components/dashboard/CreateBot";
import SetOpenAIKey from "@/components/dashboard/SetOpenAIKey";
import PurgeChats from "@/components/dashboard/PurgeChats";
import DeleteBot from "@/components/dashboard/DeleteBot";
import { useEffect, useState } from "react";

export default function Home() {
  const [isKeyPresent, setIsKeyPresent] = useState(false);

  useEffect(() => {
    fetch("/api/check_key")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "ok") {
          setIsKeyPresent(true);
        }
      });
  }, []);

  return (
    <>
      <Sidebar />
      <Wrapper>
        <div className="text-center">
          <h1 className="mb-4 text-4xl font-extrabold leading-none tracking-tight text-gray-900 md:text-5xl">
            Welcome to Embedchain Playground
          </h1>
          <p className="mb-6 text-lg font-normal text-gray-500 lg:text-xl">
            Embedchain is a Data Platform for LLMs - Load, index, retrieve, and sync any unstructured data
            dataset
          </p>
        </div>
        <div
          className={`pt-6 gap-y-4 gap-x-8 ${
            isKeyPresent ? "grid lg:grid-cols-2" : "w-[50%] mx-auto"
          }`}
        >
          <SetOpenAIKey setIsKeyPresent={setIsKeyPresent} />
          {isKeyPresent && (
            <>
              <CreateBot />
              <DeleteBot />
              <PurgeChats />
            </>
          )}
        </div>
      </Wrapper>
    </>
  );
}
