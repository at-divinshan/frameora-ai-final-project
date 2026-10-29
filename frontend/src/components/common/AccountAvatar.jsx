import useAuth from "../../hooks/useAuth";

export default function AccountAvatar({ className = "" }) {
  const { user, pictureUrl } = useAuth();
  return <span className={`${className} account-avatar`} aria-hidden="true">
    {pictureUrl ? <img src={pictureUrl} alt="" /> : user?.name?.trim().charAt(0).toUpperCase()}
  </span>;
}
