import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const navigation=vi.hoisted(()=>({replace:vi.fn(),refresh:vi.fn()}));
vi.mock("next/navigation",()=>({useRouter:()=>navigation}));
import { ForgotPasswordForm } from "@/components/forgot-password-form";
import { ResetPasswordForm } from "@/components/reset-password-form";
afterEach(()=>{vi.unstubAllGlobals();navigation.replace.mockReset();navigation.refresh.mockReset();});
describe("password recovery forms",()=>{
 it("shows the same safe forgot-password confirmation",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify({message:"accepted"}),{status:202,headers:{"content-type":"application/json"}})));render(<ForgotPasswordForm/>);fireEvent.change(screen.getByLabelText("Work email"),{target:{value:"owner@example.com"}});fireEvent.click(screen.getByRole("button",{name:"Send reset link"}));expect(await screen.findByRole("status")).toHaveTextContent("If that account exists");});
 it("submits the token and matching new password",async()=>{const fetchMock=vi.fn().mockResolvedValue(new Response("{}",{status:200}));vi.stubGlobal("fetch",fetchMock);render(<ResetPasswordForm token="private-reset-token-value-1234567890"/>);fireEvent.change(screen.getByLabelText("New password"),{target:{value:"new-correct-horse-battery"}});fireEvent.change(screen.getByLabelText("Confirm new password"),{target:{value:"new-correct-horse-battery"}});fireEvent.click(screen.getByRole("button",{name:"Reset password"}));await waitFor(()=>expect(navigation.replace).toHaveBeenCalledWith("/login?reset=success"));expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({token:"private-reset-token-value-1234567890",password:"new-correct-horse-battery"});});
});
