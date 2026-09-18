import { useState, useRef, useEffect } from "react";
import keycloak from "@/keycloak";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { LogOut, Mail, Shield, ChevronUp } from "lucide-react";

function UserCard() {
  const [isOpen, setIsOpen] = useState(false);
  const cardRef = useRef(null);

  // Get user info from keycloak token
  const tokenParsed = keycloak.tokenParsed;
  const user = {
    username: tokenParsed?.preferred_username,
    email: tokenParsed?.email,
    firstName: tokenParsed?.given_name,
    lastName: tokenParsed?.family_name,
    roles: tokenParsed?.realm_access?.roles || [],
    fullName: tokenParsed?.name,
  };

  // Close card when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (cardRef.current && !cardRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Get initials for avatar
  const getInitials = () => {
    if (user?.firstName && user?.lastName) {
      return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase();
    }
    if (user?.username) {
      return user.username.slice(0, 2).toUpperCase();
    }
    return "U";
  };

  // Logout function
  const logout = () => {
    keycloak.logout({
      redirectUri: window.location.origin + "/",
    });
  };

  return (
    <div className="relative" ref={cardRef}>
      {/* Avatar Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        title="User Settings"
        className="flex  items-center gap-2 p-1 rounded-full bg-secondary dark:bg-slate-800/50 border border-border dark:border-slate-700/50 hover:bg-accent dark:hover:bg-slate-700/50 hover:border-border dark:hover:border-slate-600/50 transition-all duration-200 cursor-pointer group"
      >
        <Avatar className="h-8 w-8 border-2 border-primary/30 dark:border-teoco-real-blue/50 group-hover:border-primary/60 dark:group-hover:border-teoco-real-blue transition-colors" onClick={() => setIsOpen(!isOpen)}>
          <AvatarFallback className="bg-primary dark:bg-gradient-to-br dark:from-teoco-real-blue dark:to-teoco-navy-blue text-primary-foreground dark:text-white text-xs font-semibold">
            {getInitials()}
          </AvatarFallback>
        </Avatar>
        {/* <ChevronUp 
          className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${isOpen ? '' : 'rotate-180'}`} 
        /> */}
      </button>

      {/* Dropdown Card */}
      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-72 bg-popover dark:bg-slate-900 border border-border dark:border-slate-700/50 rounded-xl shadow-2xl shadow-black/50 overflow-visible z-[100] animate-in fade-in slide-in-from-bottom-2 duration-200">
          {/* Header with gradient */}
          <div className="bg-primary dark:bg-gradient-to-r dark:from-teoco-real-blue dark:to-teoco-navy-blue p-4 rounded-xl">
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12 border-2 border-primary-foreground/20 dark:border-white/20">
                <AvatarFallback className="bg-primary-foreground/10 dark:bg-white/10 text-primary-foreground dark:text-white text-lg font-semibold">
                  {getInitials()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-primary-foreground dark:text-white font-semibold truncate">
                  {user?.fullName || user?.username || "User"}
                </p>
                <p className="text-primary-foreground/70 dark:text-white/70 text-sm truncate">
                  @{user?.username}
                </p>
              </div>
            </div>
          </div>

          {/* User Info */}
          <div className="p-3 space-y-1">
            {user?.email && (
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-secondary dark:bg-slate-800/50 border border-border dark:border-slate-700/30">
                <Mail className="w-4 h-4 text-teoco-real-blue flex-shrink-0" />
                <span className="text-muted-foreground dark:text-gray-300 text-sm truncate">{user.email}</span>
              </div>
            )}
            
            {/* {user?.roles && user.roles.length > 0 && (
              <div className="flex items-start gap-3 px-3 py-2.5 rounded-lg bg-slate-800/50 border border-slate-700/30">
                <Shield className="w-4 h-4 text-teoco-real-blue flex-shrink-0 mt-0.5" />
                <div className="flex flex-wrap gap-1.5">
                  {user.roles.filter(role => !role.startsWith('default-')).slice(0, 3).map((role, index) => (
                    <span 
                      key={index}
                      className="px-2 py-0.5 text-xs bg-teoco-real-blue/20 text-teoco-real-blue border border-teoco-real-blue/30 rounded-full"
                    >
                      {role}
                    </span>
                  ))}
                  {user.roles.filter(role => !role.startsWith('default-')).length > 3 && (
                    <span className="px-2 py-0.5 text-xs bg-slate-700/50 text-gray-400 rounded-full">
                      +{user.roles.filter(role => !role.startsWith('default-')).length - 3} more
                    </span>
                  )}
                </div>
              </div>
            )} */}
          </div>

          {/* Divider */}
          <div className="mx-3 border-t border-border dark:border-slate-700/50" />

          {/* Logout Button */}
          <div className="p-3">
            <button
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 transition-all duration-200 cursor-pointer group"
            >
              <LogOut className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              <span className="font-medium">Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserCard;

