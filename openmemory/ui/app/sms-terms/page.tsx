"use client";

import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { motion } from "framer-motion";

const TermsSection = ({ title, children, isListItem = false }: { title: string, children: React.ReactNode, isListItem?: boolean }) => (
    <div className={isListItem ? "ml-4" : ""}>
      <h3 className="font-semibold text-foreground mb-2">{title}</h3>
      <div className="space-y-2 text-muted-foreground">{children}</div>
    </div>
);

export default function SmsTermsPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* Background Animation */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="sms-terms-particles" className="h-full w-full" interactive={false} particleCount={50} />
      </div>

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-16 max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="p-8 md:p-12"
        >
          <div className="text-center mb-16">
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4">
              SMS Terms of Service
            </h1>
            <p className="text-lg text-muted-foreground">
              Jean Memory SMS Program
            </p>
          </div>

          <div className="space-y-8 text-base leading-relaxed prose dark:prose-invert mx-auto">
            <ol className="list-decimal list-outside space-y-6">
              <li>
                <TermsSection title="Program Description">
                  <p>
                    This service sends you one-time verification codes and allows you to interact with your Jean Memory assistant via text message. All messages after the initial opt-in are initiated by you.
                  </p>
                </TermsSection>
              </li>
              <li>
                <TermsSection title="Opting Out">
                  <p>
                    You can cancel the SMS service at any time. Just text "STOP" to the short code. After you send the SMS message "STOP" to us, we will send you an SMS message to confirm that you have been unsubscribed. After this, you will no longer receive SMS messages from us. If you want to join again, just sign up as you did the first time and we will start sending SMS messages to you again.
                  </p>
                </TermsSection>
              </li>
              <li>
                <TermsSection title="Help">
                  <p>
                    If you are experiencing issues with the messaging program you can reply with the keyword HELP for more assistance, or you can get help directly at <a href="mailto:contact@jeantechnologies.com" className="text-primary underline">contact@jeantechnologies.com</a>.
                  </p>
                </TermsSection>
              </li>
              <li>
                 <TermsSection title="Carrier Liability">
                  <p>
                    Carriers are not liable for delayed or undelivered messages.
                  </p>
                </TermsSection>
              </li>
              <li>
                 <TermsSection title="Rates and Frequency">
                  <p>
                    As always, message and data rates may apply for any messages sent to you from us and to us from you. Message frequency varies based on your usage. If you have any questions about your text plan or data plan, it is best to contact your wireless provider.
                  </p>
                </TermsSection>
              </li>
              <li>
                <TermsSection title="Privacy">
                  <p>
                    If you have any questions regarding privacy, please read our privacy policy: <a href="https://jonathan-politzki.github.io/jean-privacy-policy/" target="_blank" rel="noopener noreferrer" className="text-primary underline">https://jonathan-politzki.github.io/jean-privacy-policy/</a>.
                  </p>
                </TermsSection>
              </li>
            </ol>
          </div>
        </motion.div>
      </div>
    </div>
  );
} 