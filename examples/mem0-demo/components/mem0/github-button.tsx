import { cn } from "@/lib/utils";

const GithubButton = ({ url, className, text }: { url: string, className?: string, text?: string }) => {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn("flex items-center bg-black text-white rounded-full shadow-lg hover:bg-gray-800 transition border border-gray-700", className)}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="white"
        className="w-5 h-5 md:w-6 md:h-6"
      >
        <path
          fillRule="evenodd"
          d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.167 6.839 9.49.5.09.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.603-3.369-1.34-3.369-1.34-.455-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.004.07 1.532 1.032 1.532 1.032.892 1.528 2.341 1.087 2.91.832.091-.647.35-1.086.636-1.337-2.22-.253-4.555-1.11-4.555-4.943 0-1.092.39-1.984 1.03-2.682-.103-.253-.447-1.273.098-2.654 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.8c.85.004 1.705.114 2.504.334 1.91-1.294 2.75-1.025 2.75-1.025.546 1.381.202 2.401.099 2.654.641.698 1.03 1.59 1.03 2.682 0 3.842-2.337 4.687-4.564 4.936.36.31.679.919.679 1.852 0 1.337-.012 2.416-.012 2.743 0 .267.18.576.688.477C19.138 20.163 22 16.414 22 12c0-5.523-4.477-10-10-10z"
          clipRule="evenodd"
        />
      </svg>
      {text && <span className="ml-2">{text}</span>}
    </a>
  );
};

export default GithubButton;
