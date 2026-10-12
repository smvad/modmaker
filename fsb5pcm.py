#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка FSB5-контейнера с PCM16 для resources.resource (LED HEARTS).

Все 371 штатных клипа — FSB5 v1 + Vorbis, но кодировщика Vorbis/FSB5
в открытом виде нет. FSB5 при этом понимает сырой PCM16
(SoundFormat.PCM16 = 2), а Unity отдаёт блобы из .resource в FMOD как есть —
поэтому свой звук можно вшить как FSB5/PCM16 чистым Python, без FMOD SDK.

Формат (little-endian, по парсеру fsb5 1.0):
  base header: 'FSB5' u32 version=1, u32 numSamples=1, u32 sampleHeadersSize=8,
    u32 nameTableSize=0, u32 dataSize, u32 mode=2, 8+16+8 нулей;
  sample entry u64: bit0 next_chunk=0, bits[1:5] код частоты (8=44100, 9=48000),
    bit5 channels-1, bits[6:34] dataOffset/16=0, bits[34:64] число фреймов.
  data: сырой PCM16, хвост добит нулями так, чтобы весь блоб был кратен 16
  (в оригинальном resources.resource все смещения/размеры кратны 16).

Ограничения входа (как у внешнего dlc-загрузчика игры):
  WAV PCM 16-bit, 44100/48000 Гц, моно/стерео.
"""
from __future__ import annotations

import struct
import wave

RATE_CODES = {44100: 8, 48000: 9}
PCM16_MODE = 2


def read_wav_pcm16(path) -> tuple[bytes, int, int, int]:
    """(pcm_bytes, channels, rate, frames). Только PCM16."""
    with wave.open(str(path), "rb") as w:
        if w.getcomptype() != "NONE" or w.getsampwidth() != 2:
            raise ValueError(f"{path}: нужен WAV PCM 16-bit")
        rate = w.getframerate()
        if rate not in RATE_CODES:
            raise ValueError(f"{path}: частота {rate} Гц, нужна 44100/48000")
        channels = w.getnchannels()
        if channels not in (1, 2):
            raise ValueError(f"{path}: каналов {channels}, нужно 1-2")
        frames = w.getnframes()
        pcm = w.readframes(frames)
    if len(pcm) != frames * channels * 2:
        raise ValueError(f"{path}: обрезанный WAV")
    return pcm, channels, rate, frames


def build_fsb5_pcm16(pcm: bytes, channels: int, rate: int, frames: int) -> bytes:
    if channels not in (1, 2):
        raise ValueError("channels 1-2")
    entry = ((RATE_CODES[rate] & 0xF) << 1) | ((channels - 1) << 5) | (frames << 34)
    pad = (-(68 + len(pcm))) % 16
    data = pcm + b"\x00" * pad
    header = struct.pack("<4sIIIIII", b"FSB5", 1, 1, 8, 0, len(data), PCM16_MODE)
    header += b"\x00" * (8 + 16 + 8)
    blob = header + struct.pack("<Q", entry) + data
    assert len(blob) % 16 == 0
    return blob


def parse_fsb5_pcm16(blob: bytes) -> tuple[bytes, int, int, int]:
    """Обратная проверка: (pcm_без_паддинга, channels, rate, frames)."""
    if blob[:4] != b"FSB5":
        raise ValueError("нет сигнатуры FSB5")
    ver, nsub, shdr, ntable, dsize, mode = struct.unpack("<IIIIII", blob[4:28])
    if (ver, nsub, shdr, ntable, mode) != (1, 1, 8, 0, PCM16_MODE):
        raise ValueError(f"чужой FSB5: ver={ver} nsub={nsub} mode={mode}")
    entry, = struct.unpack("<Q", blob[60:68])
    if entry & 1:
        raise ValueError("неожиданные чанки")
    rate = {8: 44100, 9: 48000}[(entry >> 1) & 0xF]
    channels = ((entry >> 5) & 1) + 1
    frames = entry >> 34
    pcm = blob[68:68 + frames * channels * 2]
    if len(pcm) != frames * channels * 2:
        raise ValueError("блоб обрезан")
    return pcm, channels, rate, frames
