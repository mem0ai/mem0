export default function HumanWrapper({ children }) {
  return (
    <>
      <div className="rounded-lg">
        <div className="flex items-center justify-start flex-row-reverse">
          <div className="flex items-center justify-center h-10 w-10 rounded-full bg-blue-800 text-white flex-shrink-0">
            H
          </div>
          <div className="mr-3 text-sm bg-blue-200 py-2 px-4 shadow-lg rounded-xl">
            <div>{children}</div>
          </div>
        </div>
      </div>
    </>
  );
}
