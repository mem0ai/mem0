export async function loadPeer(
  pkg: string,
  label: string,
  load: () => Promise<any>,
): Promise<any> {
  try {
    return await load();
  } catch {
    throw new Error(
      `The '${pkg}' package is required to use the ${label}. Install it with: npm install ${pkg}`,
    );
  }
}
