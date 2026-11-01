#pragma once
// SHA-256 of a block, for the two modules' art caches (K1RuntimeAssets.cpp,
// K1ControllerStandalone.cpp; audit S-8). Needs <windows.h> and <bcrypt.h> before it.
#include <cstdint>

// The provider is opened once a thread: a set is some 2,100 files, each hashed on its way to
// the cache, and opening it for every one of them was measurable.
template <class Key>
inline bool KmrpSha256(const unsigned char* data, unsigned size, Key& result)
{
    static thread_local BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    if (!algorithm && BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) {
        algorithm = nullptr;
        return false;
    }
    const bool ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
        BCryptHashData(hash, const_cast<unsigned char*>(data), size, 0) >= 0 &&
        BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    return ok;
}
