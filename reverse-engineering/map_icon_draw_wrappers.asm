bits 32

; Position-independent wrappers for the two coordinate getters used only by
; the full-screen map. EBX is the CUIMap object at all three patched call sites.

wrapper_world_to_map:
    push ebp
    mov ebp, esp
    push esi

    push dword [ebp + 0x18]
    push dword [ebp + 0x14]
    push dword [ebp + 0x10]
    push dword [ebp + 0x0c]
    push dword [ebp + 0x08]
    mov edx, 0x00578e00
    call edx
    test eax, eax
    jz .done

    push eax
    mov esi, [ebp + 0x14]
    mov eax, [esi]
    imul eax, dword [ebx + 0x0c]
    add eax, 220
    cdq
    mov ecx, 440
    idiv ecx
    mov [esi], eax

    mov esi, [ebp + 0x18]
    mov eax, [esi]
    imul eax, dword [ebx + 0x10]
    add eax, 128
    cdq
    mov ecx, 256
    idiv ecx
    mov [esi], eax
    pop eax

.done:
    pop esi
    pop ebp
    ret 0x14

times 0x80 - ($ - $$) db 0x90

wrapper_cached_map_point:
    push ebp
    mov ebp, esp
    push esi

    push dword [ebp + 0x10]
    push dword [ebp + 0x0c]
    push dword [ebp + 0x08]
    mov edx, 0x005791b0
    call edx
    test eax, eax
    jz .done

    push eax
    mov esi, [ebp + 0x0c]
    mov eax, [esi]
    imul eax, dword [ebx + 0x0c]
    add eax, 220
    cdq
    mov ecx, 440
    idiv ecx
    mov [esi], eax

    mov esi, [ebp + 0x10]
    mov eax, [esi]
    imul eax, dword [ebx + 0x10]
    add eax, 128
    cdq
    mov ecx, 256
    idiv ecx
    mov [esi], eax
    pop eax

.done:
    pop esi
    pop ebp
    ret 0x0c

times 0x100 - ($ - $$) db 0x90
