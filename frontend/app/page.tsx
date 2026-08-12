"use client";
import {useEffect} from "react";
import {useRouter} from "next/navigation";
import {token} from "@/lib/api";
export default function Home(){const router=useRouter();useEffect(()=>router.replace(token()?"/operations":"/login"),[router]);return <div className="boot"><div className="spinner"/>Loading 5G RCA Copilot…</div>}
