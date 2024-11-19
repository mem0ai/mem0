import { Button } from "@/components/ui/button";
import { ChevronRight, X, RefreshCcw, Settings } from "lucide-react";
import { Dispatch, SetStateAction, useContext, useEffect, useState } from "react";
import GlobalContext from "../contexts/GlobalContext";
import { Input } from "./ui/input";

const Header = (props: {
  setIsSettingsOpen: Dispatch<SetStateAction<boolean>>;
}) => {
  const { setIsSettingsOpen } = props;
  const { selectUserHandler, clearUserHandler, selectedUser, clearConfiguration } = useContext(GlobalContext);
  const [userId, setUserId] = useState<string>("");

  const handleSelectUser = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUserId(e.target.value);
  };

  const handleClearUser = () => {
    clearUserHandler();
    setUserId("");
  };

  const handleSubmit = () => {
    selectUserHandler(userId);
  };

  // New function to handle key down events
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault(); // Prevent form submission if it's in a form
      handleSubmit();
    }
  };

  useEffect(() => {
    if (selectedUser) {
      setUserId(selectedUser);
    }
  }, [selectedUser]);

  return (
    <>
      <header className="border-b p-4 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-xl font-semibold">Mem0 Assistant</span>
        </div>
        <div className="flex items-center space-x-2 text-sm">
          <div className="flex">
            <Input 
              placeholder="UserId" 
              className="w-full rounded-3xl pr-6 pl-4" 
              value={userId}
              onChange={handleSelectUser} 
              onKeyDown={handleKeyDown} // Attach the key down handler here
            />
            <Button variant="ghost" size="icon" onClick={handleClearUser} className="relative hover:bg-transparent hover:text-neutral-400 right-8">
              <X className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={handleSubmit} className="relative right-6">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="icon" onClick={clearConfiguration}>
              <RefreshCcw className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsSettingsOpen(true)}
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>
    </>
  );
};

export default Header;
