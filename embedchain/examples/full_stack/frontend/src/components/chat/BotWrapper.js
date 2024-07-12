export default function BotWrapper({ children }) {
  return (
    <>
      <div className="rounded-lg">
        <div className="flex flex-row items-center">
          <div className="flex items-center justify-center h-10 w-10 rounded-full bg-black text-white flex-shrink-0">
            B
          </div>
          <div className="ml-3 text-sm bg-white py-2 px-4 shadow-lg rounded-xl">
            <div>{children}</div>
          </div>
        </div>
      </div>
    </>
  );
}
