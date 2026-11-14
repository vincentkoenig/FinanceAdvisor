// Brücke zu navigator.credentials: Der Server liefert die Passkey-Optionen als JSON mit base64url-Texten,
// der Browser braucht Binärdaten - und umgekehrt bei der Antwort. Wird erst geladen, wenn jemand
// einen Passkey einrichtet oder sich damit anmeldet.

function toBytes(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(value.length / 4) * 4, '=');
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function toText(buffer: ArrayBuffer | null | undefined): string | undefined {
  if (!buffer) return undefined;
  let binary = '';
  new Uint8Array(buffer).forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

type Descriptor = { id: string; type: 'public-key'; transports?: AuthenticatorTransport[] };
export type CreationJSON = Omit<PublicKeyCredentialCreationOptions, 'challenge' | 'user' | 'excludeCredentials'> & {
  challenge: string; user: { id: string; name: string; displayName: string }; excludeCredentials?: Descriptor[];
};
export type RequestJSON = Omit<PublicKeyCredentialRequestOptions, 'challenge' | 'allowCredentials'> & {
  challenge: string; allowCredentials?: Descriptor[];
};

const descriptors = (list: Descriptor[] = []) => list.map((d) => ({ ...d, id: toBytes(d.id) }));

export async function createPasskey(options: CreationJSON) {
  const credential = await navigator.credentials.create({
    publicKey: {
      ...options,
      challenge: toBytes(options.challenge),
      user: { ...options.user, id: toBytes(options.user.id) },
      excludeCredentials: descriptors(options.excludeCredentials),
    },
  }) as PublicKeyCredential | null;
  if (!credential) throw new DOMException('Abgebrochen', 'NotAllowedError');
  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: toText(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: toText(response.clientDataJSON),
      attestationObject: toText(response.attestationObject),
      transports: response.getTransports?.() ?? [],
    },
  };
}

export async function getPasskey(options: RequestJSON) {
  const credential = await navigator.credentials.get({
    publicKey: { ...options, challenge: toBytes(options.challenge), allowCredentials: descriptors(options.allowCredentials) },
  }) as PublicKeyCredential | null;
  if (!credential) throw new DOMException('Abgebrochen', 'NotAllowedError');
  const response = credential.response as AuthenticatorAssertionResponse;
  return {
    id: credential.id,
    rawId: toText(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: toText(response.clientDataJSON),
      authenticatorData: toText(response.authenticatorData),
      signature: toText(response.signature),
      userHandle: toText(response.userHandle),
    },
  };
}
