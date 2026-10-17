"""Disposable parser process with memory and wall-clock bounds, no executable uploads."""

import asyncio
import base64
import json
import os
import sys


async def parse_isolated(name, content, timeout=30):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.ingestion.sandbox",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH", "VIRTUAL_ENV"}
        },
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(
                json.dumps({"name": name, "content": base64.b64encode(content).decode()}).encode()
            ),
            timeout,
        )
        if process.returncode != 0:
            raise ValueError("Document parser rejected the file or exceeded its resource budget.")
        from app.ingestion.parsing import Section

        return [Section(**section) for section in json.loads(output)]
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def memory_limit():
    limit = 512 * 1024 * 1024
    if os.name != "nt":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        return None
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("minimum", ctypes.c_size_t),
            ("maximum", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", ctypes.c_uint64 * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.basic.flags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.process_memory = limit
    if not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise RuntimeError("Cannot establish parser memory limit")
    if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(-1)):
        raise RuntimeError("Cannot isolate parser process")
    return job  # Keep the handle alive until this disposable process exits.


if __name__ == "__main__":
    job_handle = memory_limit()
    from dataclasses import asdict

    from app.ingestion.parsing import parse, validate_file

    request = json.loads(sys.stdin.buffer.read(30 * 1024 * 1024))
    data = base64.b64decode(request["content"], validate=True)
    validate_file(request["name"], data, 20)
    result = parse(request["name"], data)
    sys.stdout.write(json.dumps([asdict(section) for section in result]))
